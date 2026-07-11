/**
 * Personnel page JavaScript for HS Admin portal
 */
jQuery(document).ready(function ($) {
    var tbl_active = $("#tbl_active").DataTable();
    var tbl_inactive = $("#tbl_inactive").DataTable();

    var datatableButtons = [
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
    ];

    var datatableDom = 'B<"float-left mt-3 mb-3"l><"float-right mt-3"f><"row clear">rt<"row"<"col-6"i><"col-6 float-right"p>>';

    function get_inactive() {
        tbl_inactive.destroy();

        tbl_inactive = $("#tbl_inactive").DataTable({
            language: {
                'emptyTable': 'No records found.'
            },
            dom: datatableDom,
            buttons: datatableButtons,
            ajax: '/highschool_admin/api/personnel/?format=datatables&status=inactive',
            columns: [
                {
                    'render': function (data, type, row, meta) {
                        return row.name;
                    }
                },
                {
                    'width': '25%',
                    'render': function (data, type, row, meta) {
                        return row.highschool;
                    }
                },
                {
                    'width': '15%',
                    'render': function (data, type, row, meta) {
                        return row.position;
                    }
                },
                {
                    'width': '15%',
                    'render': function (data, type, row, meta) {
                        return row.status;
                    }
                }
            ]
        });
    }

    function get_active() {
        tbl_active.destroy();

        tbl_active = $("#tbl_active").DataTable({
            language: {
                'emptyTable': 'No records found.'
            },
            dom: datatableDom,
            buttons: datatableButtons,
            ajax: '/highschool_admin/api/personnel/?format=datatables',
            columns: [
                {
                    'render': function (data, type, row, meta) {
                        return row.name;
                    }
                },
                {
                    'width': '25%',
                    'render': function (data, type, row, meta) {
                        return row.highschool;
                    }
                },
                {
                    'width': '15%',
                    'render': function (data, type, row, meta) {
                        return row.position;
                    }
                },
                {
                    'width': '15%',
                    'render': function (data, type, row, meta) {
                        return row.status;
                    }
                },
                {
                    'width': '15%',
                    'render': function (data, type, row, meta) {
                        return '<a href="#" class="ajax-add_new btn btn-primary text-white text-light btn-sm" data-parent="' +
                            row.parent_id + '" data-id="' + row.id + '" data-modal="modal-add_new" data-model="hsadministratorrole" data-updater="">Update Status</a>';
                    }
                }
            ]
        });
    }

    get_active();
    get_inactive();

    $(document).on('click', 'a.btn', function () {
        var src = $(this).attr('href');

        $("#details_src").attr('src', src);
        $('#details').modal('show');
        return false;
    });

    $('#details').on('hidden.bs.modal', function () {
        get_active();
        get_inactive();
    });
});
