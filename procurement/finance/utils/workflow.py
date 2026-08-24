def advance_workflow(obj, user):
    if obj.status == "submitted":
        obj.status = "finance_review"
        obj.checked_by = user

    elif obj.status == "finance_review":
        obj.status = "operations_review"
        obj.reviewed_by = user

    elif obj.status == "operations_review":
        obj.status = "approved"
        obj.approved_by = user
    obj.save()


def user_can_approve(user, obj):
    if obj.status == "submitted":
        return user.groups.filter(name="Finance").exists()

    elif obj.status == "finance_review":
        return user.groups.filter(name="Operations").exists()

    elif obj.status == "operations_review":
        return user.groups.filter(name="ED").exists()

    return False
