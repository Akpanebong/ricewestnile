from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.mail import send_mail
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView
from django.db.models import Sum, Q

from account.models import Profile
from core.project_models import Project
from notification.models import Notification, NotificationRecipient
from notification.utils import notify
from procurement.procureapp.forms import RequisitionForm, RequisitionItemFormSet
from procurement.procureapp.models import Requisition, RequisitionItem, Product
from procurement.procureapp.utils import render_pdf, send_html_email
from procurement.procureapp.views import _notify_next_stage, _notify_requester


@login_required(login_url='login')
def req_create(request):
    if not request.user.is_superuser and not Project.objects.filter(project_officer=request.user).exists():
        messages.warning(request,"Only Project Officers can create procurement requisitions.")
        return redirect('req_list')

    if request.method == 'POST':
        form = RequisitionForm(request.POST, user=request.user)
        formset = RequisitionItemFormSet(request.POST, instance=Requisition())
        if form.is_valid():
            po = form.save(commit=False)
            po.issued_by = po.created_by = request.user

            if po.procurement and po.procurement.project and po.procurement.project.project_officer_id != request.user.id and not request.user.is_superuser:
                messages.error(request, "Only the assigned Project Officer can request procurement from this project plan.")
                return redirect('req_create')

            po.save()
            # create RequisitionItem from selected procurement items if form did not include explicit items
            if po.procurement:
                # create items based on procurement items
                for ri in po.procurement.items.all():
                    RequisitionItem.objects.create(
                        po=po,
                        procurement_item=ri,
                        description=ri.description,
                        unit_measure=ri.unit_measure,
                        qty=ri.qty,
                        unit_price=ri.est_unit_cost,
                        delivery_date=ri.delivery_date
                    )
                # recalc total
                po.total = sum([it.line_total() for it in po.items.all()])
                po.save(update_fields=['total'])
                form.save_m2m()  # ✅ necessary for ManyToMany fields

            else:
                # if user provided inline RequisitionItem entries, save them using formset
                formset.instance = po
                if formset.is_valid():
                    form.save_m2m()  # ✅ necessary for ManyToMany fields
                    formset.save()
                    po.total = sum([it.line_total() for it in po.items.all()])
                    po.save(update_fields=['total'])
            action_url = request.build_absolute_uri(
                reverse("po_detail", args=[po.pk]))

            notify(title="Procurement Requisition Approval Required",
                   message=f"Your procurement requisition {po.number} is awaiting your review.",
                   users=[po.procurement.project.project_head], action_url=action_url,
                   source_app='procurement', category='Info')

            # Email notification
            try:
                if po.procurement.project.project_head.email:
                    send_html_email(
                        request=request,
                        subject="Procurement Requisition Approval Required",
                        recipient=po.procurement.project.project_head.email,
                        title=f"Procurement Requisition ({po.number}) requires your approval",
                        message="Follow the link below to review and approve this request.",
                        relative_link=f"/req/{po.pk}/",
                    )
            except Exception as e:
                messages.warning(request, "Email failed for {po.username}: {e}")

            messages.success(request, "Procurement requisition submitted.")
            return redirect('po_update', pk=po.pk)
    else:
        form = RequisitionForm(user=request.user)
        formset = RequisitionItemFormSet()
    return render(request, 'procurement/req_form.html',
                  {'form': form, 'formset': formset, 'title': 'Procurement Requisition Form'})


@login_required(login_url='login')
def req_update(request, pk):
    po = get_object_or_404(Requisition, pk=pk)

    if po.status == 'Approved':
        messages.warning(request, f'Oops! {po} has pass through the final approval stage,'
                                f' hence cannot be edited.')
        return redirect('po_detail', po.pk)

    if request.method == 'POST':
        form = RequisitionForm(request.POST, instance=po, user=request.user)
        formset = RequisitionItemFormSet(request.POST, instance=po, prefix='items')

        if form.is_valid() and formset.is_valid():
            po = form.save(commit=False)
            po.updated_by = request.user

            if po.status == 'Rejected':
                po.status = 'Pending'
            po.save()
            form.save_m2m()  # ✅ necessary for ManyToMany fields
            formset.save()

            # Update total
            po.refresh_from_db()
            po.total = sum(it.line_total() for it in po.items.all())
            po.save(update_fields=['total'])

            messages.success(request, f"Requisition {po.number} updated successfully.")
            return redirect('req_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RequisitionForm(instance=po, user=request.user)
        formset = RequisitionItemFormSet(instance=po, prefix='items')

    return render(request, 'procurement/req_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Requisition Update',
        'is_update': True,
        'po': po,
    })


@login_required(login_url='login')
def req_approve(request, pk):

    po = get_object_or_404(Requisition, pk=pk)

    action = request.POST.get("action")
    reason = request.POST.get("reason", "")

    if action not in ["Reviewed", "Checked", "Approved", "Rejected"]:
        messages.error(request, "Invalid action.")
        return redirect("po_detail", pk=po.pk)

    project = po.procurement.project if po.procurement else None

    project_head = project.project_head if project else None
    project_accountant = project.project_accountant if project else None
    action_url = request.build_absolute_uri(
        reverse("po_detail", args=[po.pk]))

    user = request.user

    # =========================
    # PROJECT HEAD REVIEW
    # =========================
    if (
        user == project_head
        and po.status == "Pending"
    ):

        if action == "Reviewed":

            po.reviewed_by = user
            po.reviewed_at = timezone.now()
            po.status = "Reviewed"

            if project_accountant:

                notify(title="Requisition Check Required",
                       message=f"Your requisition {po.number} is requires your review.",
                       users=[project_accountant], action_url=action_url,
                       source_app='procurement', category='Info')

                send_html_email(
                    request=request,
                    subject="Requisition Check Required",
                    recipient=project_accountant.email,
                    title=f"Requisition {po.number} requires checking",
                    message="Please review and check this requisition.",
                    relative_link=action_url,
                )

        else:

            po.status = "Rejected"
            po.rejected_by = user
            po.rejected_at = timezone.now()
            po.rejection_reason = reason

            req_notify_requester(
                po,
                f"Requisition {po.number} was rejected by Project Head.\n\nReason: {reason}"
            )

    # =========================
    # PROJECT ACCOUNTANT CHECK
    # =========================
    elif (
        user == project_accountant
        and po.status == "Reviewed"
    ):

        if action == "Checked":

            po.checked_by = user
            po.checked_at = timezone.now()
            po.status = "Checked"

            notify(title="Requisition Approval Required",
                   message=f"The requisition with {po.number} is requires your Approval.",
                   users=[project_accountant], action_url=action_url,
                   source_app='procurement', category='Info', group_name='ED')

        else:

            po.status = "Rejected"
            po.rejected_by = user
            po.rejected_at = timezone.now()
            po.rejection_reason = reason

            req_notify_requester(
                po,
                f"Requisition {po.number} was rejected by Project Accountant.\n\nReason: {reason}"
            )

    # =========================
    # EXECUTIVE DIRECTOR APPROVAL
    # =========================
    elif (
        user.groups.filter(name="ED").exists()
        and po.status == "Checked"
    ):

        if action == "Approved":

            po.approved_by = user
            po.approved_at = timezone.now()
            po.status = "Approved"

            req_notify_requester(
                po,
                f"Requisition {po.number} has been approved."
            )

        else:

            po.status = "Rejected"
            po.rejected_by = user
            po.rejected_at = timezone.now()
            po.rejection_reason = reason

            req_notify_requester(
                po,
                f"Requisition {po.number} was rejected by Executive Director."
                f"\n\nReason: {reason}"
            )

    else:

        messages.warning(
            request,
            "You cannot perform this action at this stage."
        )

        return redirect(
            "po_detail",
            pk=po.pk
        )

    po.save()

    messages.success(
        request,
        f"Requisition {po.number} {po.status.lower()} successfully."
    )

    return redirect(
        "po_detail",
        pk=po.pk
    )

def req_notify_requester(po, message):

    action_url = f"/procurement/req/{po.pk}/"

    notify(title="Requisition Approval Required",
           message=message,
           users=[po.procurement.requester], action_url=action_url,
           source_app='procurement', category='Info')

    try:
        send_mail(
            subject="ProcurementPlan Update",
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[po.procurement.requester.email],
            fail_silently=True
        )
    except:
        pass


def trash_req(request, pk, slug):
    po = get_object_or_404(Requisition, pk=pk, slug=slug)
    if request.method == 'POST':
        messages.success(request, f"Purchase Order {po} has been trashed successfully.")
        po.delete()
        return redirect('req_list')
    return render(request, 'delete_confirmation.html',
                  {'delete': po, "cancel_url": reverse('req_list')})


@method_decorator(login_required, name='dispatch')
class RequisitionListView(ListView):
    model = Requisition
    template_name = "procurement/req_list.html"
    paginate_by = 25
    context_object_name = 'po_list'
    ordering = ['-date']

    def get_queryset(self):

        queryset = (
            Requisition.objects
            .select_related(
                'procurement',
                # 'procurement__department',
                'procurement__project',
                'issued_by'
            )
            .prefetch_related('items')
            .order_by('-date')
        )

        # STATUS FILTER
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # SEARCH FILTER
        search = self.request.GET.get('search')

        if search:
            queryset = queryset.filter(
                Q(number__icontains=search) |
                Q(procurement__number__icontains=search) |
                Q(procurement__department__name__icontains=search) |
                Q(procurement__project__name__icontains=search) |
                Q(status__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        queryset = self.get_queryset()

        # FILTERS
        context['status_filter'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')

        # ANALYTICS
        context['approved_count'] = queryset.filter(
            status='Approved'
        ).count()

        context['pending_count'] = queryset.filter(
            status='Pending'
        ).count()

        context['rejected_count'] = queryset.filter(
            status='Rejected'
        ).count()

        context['grand_total'] = (
            queryset.aggregate(
                total=Sum('total')
            )['total'] or 0
        )

        context['awarded_total'] = (
            queryset.aggregate(
                total=Sum('awarded_amount')
            )['total'] or 0
        )

        return context


class RequisitionDetailView(DetailView):
    model = Requisition
    template_name = "procurement/req_detail.html"

    def get(self, request, *args, **kwargs):
        requisition = self.get_object()
        project = requisition.procurement.project if requisition.procurement else None
        rfq = requisition.rfqs.first()

        approvals = 0

        if requisition.reviewed_by and requisition.reviewed_at:
            approvals += 1

        if requisition.checked_by and requisition.checked_at:
            approvals += 1

        if requisition.approved_by and requisition.approved_at:
            approvals += 1

        total_stages = 3
        progress_percent = int((approvals / total_stages) * 100)

        context = {
            'po': requisition,
            'project_head': project.project_head if project else None,
            'project_accountant': project.project_accountant if project else None,
            'ed': Profile.objects.get(groups__name__iexact='ED'),
            # 'ed': Group.objects.get(name__iexact='ED'),
            'approvals': approvals,
            'progress_percent': progress_percent,
            'total_stages': total_stages,
            'rfq': rfq,
            # "total_amount": requisition.total,

        }
        if request.GET.get('format') == 'pdf':
            return render_pdf('procurement/requisition_pdf.html', context,
                              f'PO_{requisition.number}.pdf', request=request,)
        return self.render_to_response(context)
