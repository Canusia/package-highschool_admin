/**
 * Transcripts page JavaScript for HS Admin portal.
 *
 * Lists the admin's schools' files with term and review status, uploads a new
 * file (package-highschool_admin #15) and deletes the admin's own unreviewed
 * uploads. Free-text values are HTML-escaped before rendering.
 */
jQuery(document).ready(function ($) {
    var config = $('#transcripts-config');
    var transcriptsUrl = config.data('transcripts-url');
    var uploadUrl = config.data('upload-url');
    var deleteUrlTemplate = config.data('delete-url-template');
    var csrfToken = $('#frm_upload_transcript input[name=csrfmiddlewaretoken]').val();

    function esc(value) {
        return $('<div/>').text(value == null ? '' : value).html();
    }

    var tbl_transcripts = $("#tbl_transcripts").DataTable({
        ajax: transcriptsUrl,
        order: [],
        columns: [
            { 'render': function (d, t, row) { return esc(row.highschool); } },
            { 'render': function (d, t, row) { return esc(row.term); } },
            { 'render': function (d, t, row) { return esc(row.uploaded_on); } },
            { 'render': function (d, t, row) { return esc(row.uploaded_by); } },
            { 'render': function (d, t, row) { return esc(row.description); } },
            {
                'render': function (d, t, row) {
                    return "<a href='/highschool_admin/transcript/" + encodeURIComponent(row.id) + "'>" +
                        esc(row.file_name) + "</a>";
                }
            },
            {
                'render': function (d, t, row) {
                    return row.reviewed
                        ? '<span class="badge badge-success">Reviewed</span> ' + esc(row.reviewed_on)
                        : '<span class="badge badge-warning">Not reviewed</span>';
                }
            },
            {
                'orderable': false,
                'render': function (d, t, row) {
                    if (!row.can_delete) return '';
                    return "<button type='button' class='btn btn-sm btn-outline-danger js-delete-transcript' " +
                        "data-id='" + esc(row.id) + "' data-name='" + esc(row.file_name) + "'>Delete</button>";
                }
            }
        ]
    });

    $('a[data-toggle="tab"]').on('shown.bs.tab', function () {
        $($.fn.dataTable.tables(true)).DataTable().columns.adjust();
    });

    function showStatus(kind, html) {
        $('#upload_status').html('<div class="alert alert-' + kind + ' mt-2">' + html + '</div>');
    }

    $('#frm_upload_transcript').on('submit', function (e) {
        e.preventDefault();
        var form = this;
        var button = $(form).find('button[type=submit]').prop('disabled', true);
        showStatus('info', 'Uploading&hellip;');

        $.ajax({
            url: uploadUrl,
            type: 'POST',
            data: new FormData(form),
            processData: false,
            contentType: false,
            success: function (response) {
                showStatus('success', esc(response.message));
                form.reset();
                tbl_transcripts.ajax.reload(null, false);
            },
            error: function (xhr) {
                var body = xhr.responseJSON || {};
                var lines = [esc(body.message || 'Upload failed. Please try again.')];
                $.each(body.errors || {}, function (field, messages) {
                    lines.push(esc(messages.join(' ')));
                });
                showStatus('danger', lines.join('<br>'));
            },
            complete: function () { button.prop('disabled', false); }
        });
    });

    $('#tbl_transcripts').on('click', '.js-delete-transcript', function () {
        var id = $(this).data('id');
        if (!confirm('Delete ' + $(this).data('name') + '?')) return;

        $.ajax({
            url: deleteUrlTemplate.replace('00000000-0000-0000-0000-000000000000', id),
            type: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
            success: function () { tbl_transcripts.ajax.reload(null, false); },
            error: function (xhr) {
                alert((xhr.responseJSON && xhr.responseJSON.message) || 'Unable to delete this file.');
            }
        });
    });
});
