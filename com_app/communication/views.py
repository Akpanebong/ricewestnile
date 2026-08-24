from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, FormView, TemplateView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from notification.models import Notification
from notification.utils import notify
from .models import MonthlyPresentation, Report, FocusArea, SubGroup
from .forms import PresentationForm, ReportForm, ReportReviewForm, ReportCommentForm, PresentationReplyForm
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Value, CharField
from itertools import chain
from django.utils.timezone import now
from .models import SubGroup, FocusArea
from .forms import SubGroupForm
from account.templatetags.custom_tags import has_group
from .utils import send_notification_email, can_submit_presentation, check_report_deadline
from smtplib import SMTPException  # for catching email sending errors


class DashboardView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):

        # Fetch data separately
        presentations = MonthlyPresentation.objects.annotate(
            activity_type=Value('Presentation', output_field=CharField())
        )

        reports = Report.objects.annotate(
            activity_type=Value('Report', output_field=CharField())
        )

        # MERGE and SORT by date_sent (descending)
        recent_activities = sorted(
            chain(presentations, reports),
            key=lambda x: x.date_sent,
            reverse=True
        )

        context = {
            'presentations_count': presentations.count(),
            'reports_count': reports.count(),
            'review_count': Report.objects.filter(
                received=False, status__in=['SUBMITTED', 'UNDER_REVIEW']
            ).count(),
            'recent_activities': recent_activities[:10],  # limit to 10 recent
        }

        return render(request, 'communication/dashboard.html', context)


class PresentationListView(LoginRequiredMixin, ListView):
    model = MonthlyPresentation
    template_name = 'communication/presentation_list.html'
    paginate_by = 25
    context_object_name = 'presentations'


class PresentationCreateView(LoginRequiredMixin, CreateView):
    model = MonthlyPresentation
    form_class = PresentationForm
    template_name = 'communication/presentation_form_create.html'
    success_url = reverse_lazy('comm:presentations')

    def dispatch(self, request, *args, **kwargs):
        today = timezone.now().date()
        allowed, message = can_submit_presentation(today)

        if not allowed:
            return HttpResponseForbidden(message)

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.sent_by = self.request.user
        obj.save()
        messages.success(self.request, "Presentation uploaded successfully.")
        return super().form_valid(form)


def presentation_reply(request, pk, slug):

    if (not request.user.can_review or has_group(request.user, "Reviewers") or
            has_group(request.user, "Communications") or request.user.is_CMT):
        messages.info(request, "You are not authorized to reply to this presentation.")
        return redirect('comm:presentations')

    presentation = get_object_or_404(MonthlyPresentation, pk=pk, slug=slug)
    if request.method == 'POST':
        form = PresentationReplyForm(request.POST, instance=presentation)
        if form.is_valid():
            reply = form.cleaned_data['reply']
            presentation.reply = reply
            presentation.received = True
            presentation.save()  # Save reply first

            subject = f"Reply to: {presentation}"
            msg = f"""
                Dear {presentation.sent_by},
                
                You are receiving this mail in response to your presentation submitted on {presentation.date_sent}.
                
                {reply}
                
                RICE WEST NILE COMMUNICATION TEAM. {now().date()}
            """
            email_sent = False
            try:
                send_notification_email(subject, msg, presentation.sent_by.email)
                email_sent = True
                messages.success(request, "Presentation reply sent successfully.")
            except SMTPException:
                messages.warning(request, "Presentation saved, but email could not be sent due to a mail server issue.")
            except Exception as e:
                # Catch other network/email-related issues
                messages.warning(request, f"Presentation saved, but email failed: {str(e)}")

            # Save notification in DB regardless of email success
            notify(
                title=subject,
                message=msg,
                users=presentation.sent_by,
                action_url='/communication/presentations/'
            )

            return redirect('comm:presentations')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PresentationReplyForm(instance=presentation)

    return render(
        request,
        'communication/presentation_form_reply.html',
        {'form': form, 'presentation': presentation, 'is_update': True}
    )


class ReportListView(LoginRequiredMixin, ListView):
    model = Report
    template_name = 'communication/report_list.html'
    paginate_by = 25
    context_object_name = 'reports'


class ReportCreateView(LoginRequiredMixin, CreateView):
    model = Report
    form_class = ReportForm
    template_name = 'communication/report_form.html'
    success_url = reverse_lazy('comm:reports')

    def form_invalid(self, form):
        # Show all errors properly in template
        for field, errors in form.errors.items():
            for error in errors:
                if field != '__all__':
                    messages.error(self.request, f"{field.title()} : {error}")
                else:
                    messages.error(self.request, error)

        return super().form_invalid(form)

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.sent_by = self.request.user
        obj.save()

        messages.success(self.request, "Report submitted successfully.")
        return super().form_valid(form)


def subgroups_for_focus_area(request, focus_area_id):
    subgroups = SubGroup.objects.filter(focus_area_id=focus_area_id).values('id','name')
    return JsonResponse(list(subgroups), safe=False)


class ReportDetailView(LoginRequiredMixin, DetailView):
    model = Report
    template_name = 'communication/report_detail.html'
    context_object_name = 'report'


class ReviewPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.groups.filter(name='REVIEW').exists() or self.request.user.can_review


class ReviewQueueView(LoginRequiredMixin, ReviewPermissionMixin, ListView):
    model = Report
    template_name = 'communication/review_queue.html'
    context_object_name = 'reports'
    paginate_by = 25

    def get_queryset(self):
        return Report.objects.filter(status__in=['SUBMITTED', 'UNDER_REVIEW'])


class ReportReviewView(LoginRequiredMixin, ReviewPermissionMixin, View):
    def get(self, request, pk):
        report = get_object_or_404(Report, pk=pk)
        form = ReportReviewForm(instance=report)
        comment_form = ReportCommentForm()
        return render(request, 'communication/report_review.html', {
            'report': report,
            'form': form,
            'comment_form': comment_form,
        })

    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk)

        form = ReportReviewForm(request.POST, instance=report)
        comment_form = ReportCommentForm(request.POST)

        # Handle review saving
        if form.is_valid():
            obj = form.save(commit=False)
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
            obj.received = True
            messages.success(request, "Report updated.")
            obj.save()

        # Handle comment saving
        if comment_form.is_valid() and comment_form.cleaned_data.get("content"):
            comment = comment_form.save(commit=False)
            comment.report = report
            comment.report.received = True
            comment.author = request.user
            comment.save()

        messages.success(request, "Review updated.")
        return redirect('comm:report_review', report.pk)




class SubGroupCreateView(View):
    def post(self, request, *args, **kwargs):
        focus_area_id = request.POST.get('focus_area_id')
        focus_area = get_object_or_404(FocusArea, id=focus_area_id)

        form = SubGroupForm(request.POST)
        if form.is_valid():
            subgroup = form.save(commit=False)
            subgroup.focus_area = focus_area
            subgroup.save()
            return JsonResponse({
                'success': True,
                'subgroup_name': subgroup.name,
                'subgroup_id': subgroup.id,
                'focus_area_id': focus_area.id  # <-- needed for JS
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class FocusAreaDashboardView(TemplateView):
    template_name = 'communication/subgroup_modal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['focus_areas'] = FocusArea.objects.prefetch_related('subgroups').all()
        context['form'] = SubGroupForm()
        return context


class SubGroupUpdateView(View):
    def post(self, request, pk):
        subgroup = get_object_or_404(SubGroup, pk=pk)
        form = SubGroupForm(request.POST, instance=subgroup)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False}, status=400)


class SubGroupDeleteView(View):
    def post(self, request, pk):
        subgroup = get_object_or_404(SubGroup, pk=pk)
        subgroup.delete()
        return JsonResponse({'success': True})
