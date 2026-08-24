from django.db.models import Q


def filter_notifications(queryset, request):

    keyword = request.GET.get("keyword")

    status = request.GET.get("status")

    category = request.GET.get("category")

    if keyword:

        queryset = queryset.filter(

            Q(notification__title__icontains=keyword)

            |

            Q(notification__message__icontains=keyword)

        )

    if status == "read":

        queryset = queryset.filter(

            is_read=True

        )

    elif status == "unread":

        queryset = queryset.filter(

            is_read=False

        )

    if category:

        queryset = queryset.filter(

            notification__category=category

        )

    return queryset