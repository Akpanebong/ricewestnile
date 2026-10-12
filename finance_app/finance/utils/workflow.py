from account.permissions import can_sign_without_conflict


def advance_workflow(obj, user):
    previous_signers = [obj.checked_by, obj.reviewed_by, obj.approved_by]
    if not can_sign_without_conflict(
        user,
        requester=obj.created_by,
        previous_signers=previous_signers,
    ):
        return False

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
    return True


def user_can_approve(user, obj):
    if not can_sign_without_conflict(
        user,
        requester=obj.created_by,
        previous_signers=[obj.checked_by, obj.reviewed_by, obj.approved_by],
    ):
        return False

    if obj.status == "submitted":
        return user.groups.filter(name="Finance").exists()

    elif obj.status == "finance_review":
        return user.groups.filter(name="Operations").exists()

    elif obj.status == "operations_review":
        return user.groups.filter(name="ED").exists()

    return False
