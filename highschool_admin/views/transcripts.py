from django import forms
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseNotFound, FileResponse
from django.views.decorators.http import require_POST

from cis.forms.highschool import HSTranscriptUploadForm
from cis.models.highschool import HighSchool, HighSchoolTranscript
from cis.highschool_scope import picker_queryset
from cis.menu import draw_menu
from cis.services.hs_uploads import notify_hs_upload
from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang

from .utils import get_user_highschools, get_hsadmin_menu


class HSAdminTranscriptUploadForm(HSTranscriptUploadForm):
    """cis's upload form (term, description, file rules; package-cis #56) plus
    the school, limited to the ones this admin manages. The queryset is the
    server-side check: a posted id for any other school fails validation."""
    highschool = forms.ModelChoiceField(
        queryset=HighSchool.objects.none(), label='High School')

    class Meta(HSTranscriptUploadForm.Meta):
        fields = ['highschool'] + HSTranscriptUploadForm.Meta.fields

    def __init__(self, highschools, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only schools active on the current campus, within the admin's own.
        highschools = highschools.filter(
            pk__in=picker_queryset().values('pk'))
        self.fields['highschool'].queryset = highschools
        if highschools.count() == 1:
            self.fields['highschool'].initial = highschools.first()
            self.fields['highschool'].widget = forms.HiddenInput()


def transcripts(request):
    """Transcripts list page, with the upload form (#15)."""
    return render(
        request,
        'highschool_admin/transcripts.html',
        {
            'menu': draw_menu(get_hsadmin_menu(), 'transcripts', '', 'highschool_admin'),
            'intro': portal_lang(request).from_db().get('transcripts_blurb', 'Change me'),
            'upload_form': HSAdminTranscriptUploadForm(get_user_highschools(request)),
        })


def get_transcripts(request):
    """JSON API endpoint for transcripts list."""
    highschools = get_user_highschools(request)

    transcripts_qs = HighSchoolTranscript.objects.filter(
        highschool__in=highschools
    ).select_related(
        'highschool', 'uploaded_by', 'term', 'reviewed_by'
    ).order_by('-uploaded_on')

    result = {
        'data': []
    }
    for record in transcripts_qs:
        result['data'].append({
            'uploaded_on': record.uploaded_on.strftime('%m/%d/%Y') if record.uploaded_on else '',
            'id': str(record.id),
            'uploaded_by': f'{record.uploaded_by.last_name}, {record.uploaded_by.first_name}',
            'highschool': record.highschool.name,
            'term': record.term.label if record.term_id else '',
            'description': record.description,
            'file_name': record.file_name,
            'reviewed': record.is_reviewed,
            'reviewed_on': record.reviewed_on.strftime('%m/%d/%Y') if record.reviewed_on else '',
            'can_delete': _can_delete(request, record),
        })
    return JsonResponse(result)


def _can_delete(request, record):
    """An uploader may withdraw their own file until the college reviews it."""
    return record.uploaded_by_id == request.user.pk and not record.is_reviewed


@require_POST
def upload_transcript(request):
    """Save a file a high school sends the college (#15)."""
    form = HSAdminTranscriptUploadForm(
        get_user_highschools(request), request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({
            'status': 'error',
            'message': 'Please correct the errors and try again.',
            'errors': {field: [str(e) for e in errors]
                       for field, errors in form.errors.items()},
        }, status=400)

    record = form.save(commit=False)
    record.uploaded_by = request.user
    record.save()
    notify_hs_upload(record)
    return JsonResponse({
        'status': 'success',
        'message': f'Uploaded {record.file_name}.',
    })


@require_POST
def delete_transcript(request, record_id):
    """Delete your own upload, only while it has not been reviewed (#15)."""
    record = get_object_or_404(
        HighSchoolTranscript,
        pk=record_id,
        highschool__in=get_user_highschools(request),
    )
    if not _can_delete(request, record):
        return JsonResponse({
            'status': 'error',
            'message': 'You can only delete files you uploaded that have not been reviewed yet.',
        }, status=403)

    name = record.file_name
    record.media.delete(save=False)
    record.delete()
    return JsonResponse({'status': 'success', 'message': f'Deleted {name}.'})


def download_transcript(request, record_id):
    """Download a transcript file."""
    file = get_object_or_404(
        HighSchoolTranscript,
        pk=record_id
    )

    highschools = get_user_highschools(request)

    if file.highschool not in highschools:
        return HttpResponseNotFound('File not found')

    from cis.backends.storage_backend import PrivateMediaStorage

    media_storage = PrivateMediaStorage()
    response = FileResponse(
        media_storage.open(str(file.media), 'rb'),
        content_type='application/force-download'
    )

    response['Content-Disposition'] = f'attachment; filename="{file.file_name}"'
    return response
