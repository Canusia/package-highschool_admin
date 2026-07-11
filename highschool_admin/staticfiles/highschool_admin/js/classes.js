/**
 * Classes page JavaScript for HS Admin portal
 */
$(document).ready(function () {
    // Get configuration from data attributes
    var config = $('#classes-config');
    var baseURL = config.data('classes-api');

    $(document).on("change", "form#class_section_filter :input", function () {
        load_data();
    });

    function load_data() {
        var form = $('form#class_section_filter');
        var newURL = baseURL + '&' + $(form).serialize();
        table.ajax.url(newURL).load();
    }

    var table = $('#records_classes').DataTable({
        dom: 'B<"float-left mt-3 mb-3"l><"float-right mt-3"f><"row clear">rt<"row"<"col-6"i><"col-6 float-right"p>>',
        buttons: [
            {
                extend: 'csv',
                className: 'btn btn-sm btn-primary text-white text-light',
                text: '<i class="fas fa-file-csv text-white"></i>&nbsp;CSV',
                titleAttr: 'Export Records in current View to CSV'
            },
            {
                extend: 'print',
                className: 'btn btn-sm btn-primary text-white text-light',
                text: '<i class="fas fa-print text-white"></i>&nbsp;Print',
                titleAttr: 'Print Records in Current View'
            }
        ],
        ajax: baseURL + '&' + $('form#class_section_filter').serialize(),
        serverSide: true,
        processing: true,
        stateSave: true,
        language: {
            'loadingRecords': '&nbsp;'
        },
        'lengthMenu': [30, 50, 100],
        'columns': [
            {
                'render': function (data, type, row, meta) {
                    return row.term.label;
                }
            },
            {
                'render': function (data, type, row, meta) {
                    return row.course.name + '<br>' + row.course.title;
                }
            },
            {
                'render': function (data, type, row, meta) {
                    return row.highschool_course_name;
                }
            },
            {
                'render': function (data, type, row, meta) {
                    if (row.teacher === null)
                        return '-';
                    return row.teacher.user.last_name + ', ' + row.teacher.user.first_name;
                }
            },
            {
                'render': function (data, type, row, meta) {
                    return row.class_number + ' / ' + row.section_number;
                }
            },
            null,
            null,
            {
                'searchable': false,
                'orderable': false,
                'render': function (data, type, row, meta) {
                    return "<a class='btn btn-sm btn-primary' href='/highschool_admin/class_section/" + row.id + "'>View Details</a>";
                }
            }
        ]
    });
});
