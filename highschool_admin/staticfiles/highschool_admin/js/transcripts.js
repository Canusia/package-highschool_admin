/**
 * Transcripts page JavaScript for HS Admin portal
 */
jQuery(document).ready(function ($) {
    var config = $('#transcripts-config');
    var transcriptsUrl = config.data('transcripts-url');

    var tbl_transcripts = $("#tbl_transcripts").DataTable();

    $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
        $($.fn.dataTable.tables(true)).DataTable().columns.adjust();
    });

    function get_transcripts() {
        tbl_transcripts.destroy();

        tbl_transcripts = $("#tbl_transcripts").DataTable({
            ajax: transcriptsUrl,
            columns: [
                {
                    'width': '25%',
                    'render': function (data, type, row, meta) {
                        return row.highschool;
                    }
                },
                {
                    'width': '15%',
                    'render': function (data, type, row, meta) {
                        return row.uploaded_on;
                    }
                },
                {
                    'width': '15%',
                    'render': function (data, type, row, meta) {
                        return row.uploaded_by;
                    }
                },
                {
                    'width': '25%',
                    'render': function (data, type, row, meta) {
                        return row.description;
                    }
                },
                {
                    'width': '15%',
                    'render': function (data, type, row, meta) {
                        return "<a href='/highschool_admin/transcript/" + row.id + "'>" + row.file_name + "</a>";
                    }
                }
            ]
        });
    }

    get_transcripts();
});
