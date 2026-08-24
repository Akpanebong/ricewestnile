from datetime import date, timedelta

from django.conf import settings

from risk_apps.compliance.models import ComplianceTask, ComplianceRequirement
from django.core.mail import send_mail
from django.db.models import Avg


def compliance_score(requirement):

    # ✅ Base score (FAST - DB level)
    base_score = requirement.complianceassessment_set.aggregate(
        avg=Avg('score')
    )['avg'] or 0

    # ✅ Related data
    tasks = requirement.tasks.all()
    has_verified_docs = requirement.documents.filter(is_verified=True).exists()

    # 🔻 Penalties
    overdue_count = tasks.filter(status="overdue").count()
    penalty_overdue = overdue_count * 5   # adjustable weight

    penalty_docs = 0 if has_verified_docs else 10

    # 🧠 Final score
    final_score = base_score - penalty_overdue - penalty_docs

    # ✅ Safety bounds
    final_score = max(min(final_score, 100), 0)

    return round(final_score, 2)


def update_task_status(task):
    today = date.today()

    if task.status != "completed":
        if task.due_date < today:
            task.status = "overdue"
        elif task.due_date <= today + timedelta(days=3):
            task.status = "warning"

        task.save()


def process_all_tasks():
    for task in ComplianceTask.objects.all():
        update_task_status(task)


def get_alerts():
    today = date.today()
    soon = today + timedelta(days=3)

    overdue = ComplianceTask.objects.filter(
        due_date__lt=today
    ).exclude(status="completed")

    upcoming = ComplianceTask.objects.filter(
        due_date__range=[today, soon]
    ).exclude(status="completed")

    completed = ComplianceTask.objects.filter(status="completed")

    return {
        "overdue": overdue,
        "upcoming": upcoming,
        "completed": completed
    }


def detect_compliance_gaps():
    gaps = []

    for req in ComplianceRequirement.objects.all():
        score = compliance_score(req)

        if score < 50:
            gaps.append({
                "requirement": req.title,
                "issue": "Low compliance score",
                "action": "Immediate intervention required"
            })

        if not req.documents.filter(is_verified=True).exists():
            gaps.append({
                "requirement": req.title,
                "issue": "No verified documents",
                "action": "Upload means of verification"
            })

        if req.tasks.filter(status="overdue").exists():
            gaps.append({
                "requirement": req.title,
                "issue": "Overdue compliance tasks",
                "action": "Escalate to management"
            })

    return gaps


def send_compliance_alerts():
    alerts = get_alerts()

    if alerts["overdue"].exists():
        message = "\n".join([
            f"{t.requirement.title} - Due {t.due_date}"
            for t in alerts["overdue"]
        ])

        send_mail(
            subject="🚨 Compliance Overdue Alert",
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[f"{settings.EMAIL_HOST_USER}"],
            fail_silently=True
        )