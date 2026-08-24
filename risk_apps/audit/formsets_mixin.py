from django.db import transaction
from .forms import AuditFindingFormSet, AuditEvidenceFormSet
from django.utils import timezone


class AuditFormsetMixin:

    def get_formsets(self, instance=None, post_data=None):
        if post_data:
            return {
                "finding_formset": AuditFindingFormSet(
                    post_data,
                    instance=instance,
                    prefix="finding"
                ),
                "evidence_formset": AuditEvidenceFormSet(
                    post_data,
                    instance=instance,
                    prefix="evidence"
                )
            }

        return {
            "finding_formset": AuditFindingFormSet(
                instance=instance,
                prefix="finding"
            ),
            "evidence_formset": AuditEvidenceFormSet(
                instance=instance,
                prefix="evidence"
            )
        }

    def save_formsets(self, form, context):
        finding_formset = context["finding_formset"]
        evidence_formset = context["evidence_formset"]
        today = timezone.now().date()

        if not (finding_formset.is_valid() and evidence_formset.is_valid()):
            return False

        with transaction.atomic():
            # ✅ Save parent FIRST
            self.object = form.save(commit=False)

            if self.request.user.is_authenticated:
                self.object.created_by = self.request.user

            self.object.save()

            # ✅ HANDLE FINDINGS
            findings = finding_formset.save(commit=False)
            for obj in findings:
                obj.audit = self.object  # ensure FK
                if self.request.user.is_authenticated:
                    obj.created_by = self.request.user
                    # obj.updated_at = today
                obj.save()

            for obj in finding_formset.deleted_objects:
                obj.delete()

            # ✅ HANDLE EVIDENCE
            evidences = evidence_formset.save(commit=False)
            for obj in evidences:
                obj.audit = self.object
                if self.request.user.is_authenticated:
                    obj.created_by = self.request.user
                    # obj.updated_at = today
                    # obj.updated_by = self.request.user
                obj.save()

            for obj in evidence_formset.deleted_objects:
                obj.delete()

        return True
