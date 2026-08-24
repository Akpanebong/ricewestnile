from django import forms
from django.db import transaction
from account.models import Profile
from notification.models import Notification, NotificationRecipient


class NotificationCreateForm(forms.ModelForm):

    recipients = forms.ModelMultipleChoiceField(
        queryset=Profile.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-select select2",
            }
        ),
        help_text="Leave empty if sending to all users."
    )

    send_to_all = forms.BooleanField(
        required=False,
        label="Send to all users"
    )

    class Meta:

        model = Notification

        fields = (
            "title",
            "message",
            "category",
            # "source_app",
            # "action_url",
            "attachment",
        )

        widgets = {

            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Notification title",
                }
            ),

            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                }
            ),

            "category": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "source_app": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "action_url": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "/procurement/request/12/",
                }
            ),

            "attachment": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                }
            ),

        }

    def clean(self):

        cleaned = super().clean()

        recipients = cleaned.get("recipients")

        send_to_all = cleaned.get("send_to_all")

        if not send_to_all and not recipients:
            raise forms.ValidationError(
                "Select recipients or choose Send to all."
            )

        return cleaned

    @transaction.atomic
    def save(self, created_by=None, commit=True):

        notification = super().save(commit=False)

        notification.created_by = created_by

        if commit:
            notification.save()

        if self.cleaned_data["send_to_all"]:

            users = Profile.objects.filter(
                is_active=True
            )

        else:

            users = self.cleaned_data["recipients"]

        NotificationRecipient.objects.bulk_create(

            [

                NotificationRecipient(

                    notification=notification,

                    recipient=user,

                )

                for user in users

            ],

            ignore_conflicts=True,

        )

        return notification



class NotificationUpdateForm(forms.ModelForm):

    class Meta:

        model = Notification

        fields = (

            "title",

            "message",

            "category",

            "source_app",

            "action_url",

            "attachment",

        )

        widgets = {

            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),

            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                }
            ),

            "category": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "source_app": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "action_url": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),

            "attachment": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                }
            ),

        }


class NotificationFilterForm(forms.Form):

    keyword = forms.CharField(

        required=False,

        widget=forms.TextInput(

            attrs={

                "class": "form-control",

                "placeholder": "Search notification...",

            }

        ),

    )

    status = forms.ChoiceField(

        required=False,

        choices=(

            ("", "All"),

            ("read", "Read"),

            ("unread", "Unread"),

        ),

        widget=forms.Select(

            attrs={

                "class": "form-select",

            }

        ),

    )

    category = forms.ChoiceField(

        required=False,

        choices=[("", "All Categories")] + list(Notification.Category.choices),

        widget=forms.Select(

            attrs={

                "class": "form-select",

            }

        ),

    )