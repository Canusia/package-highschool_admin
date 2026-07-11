/**
 * Students Recommendation page JavaScript for HS Admin portal
 */
jQuery(document).ready(function ($) {
    // Get configuration from data attributes
    var config = $('#students-rec-config');
    var updateRegistrationStatusUrl = config.data('update-registration-url');

    // Pay type change handler
    $(document).on('change', 'select.pay_type', function () {
        var obj = this;
        var registration_id = $(obj).attr('data-key');
        if ($(obj).val() == 'school_partial') {
            $("#id_registration_" + registration_id + "_non_student_pay_amount").removeClass('d-none');
            $("#id_registration_" + registration_id + "_non_student_pay_amount").focus();
        } else {
            $("#id_registration_" + registration_id + "_non_student_pay_amount").addClass('d-none');
        }
    });

    $(document).on('change', 'select.pay_type, input.non_student_pay_amount', function () {
        var registration_id = $(this).attr('data-id');
        var obj = $(this);

        if ($("#id_registration_" + registration_id + "_pay_type").val() == 'school_partial' &&
            $("#id_registration_" + registration_id + "_non_student_pay_amount").val() == '') {
            return;
        }

        var url = updateRegistrationStatusUrl;
        var data = {
            'id': registration_id,
            'pay_type': $("#id_registration_" + registration_id + "_pay_type").val(),
            'non_student_pay_amount': $("#id_registration_" + registration_id + "_non_student_pay_amount").val()
        };

        var glower = $(obj).parent();
        glower.blur();
        glower.addClass('myGlower_active');

        $.blockUI();
        $.ajax({
            type: "GET",
            url: url,
            data: data,
            success: function (response) {
                window.setTimeout(function () {
                    var html = "<td>" + response.student + "</td>";
                    html += "<td>" + response.psid + "</td>";
                    html += "<td>" + response.pay_type_pretty + "</td>";
                    html += "<td>" + response.class_section + "</td>";
                    html += "<td>" + response.registration_status + "</td>";

                    $(obj).parent().parent().html(html);
                    glower.toggleClass('myGlower_active');
                }, 2000);
                $.unblockUI();
            },
            error: function (xhr, status, errorThrown) {
                glower.toggleClass('myGlower_active');

                var span = document.createElement('span');
                span.innerHTML = xhr.responseJSON.errors;

                swal({
                    title: 'Unable to complete request',
                    content: span,
                    icon: 'warning'
                });

                $.unblockUI();
            }
        });
    });
});

jQuery(document).ready(function ($) {
    var tbl_pending_rec = $("#tbl_pending_rec").DataTable();
    var tbl_pending_pay_type_rec;
    var tbl_in_highschool = $("#tbl_in_highschool").DataTable();
    var tbl_registrations_in_highschool = $("#tbl_registrations_in_highschool").DataTable();

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

    $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
        $($.fn.dataTable.tables(true)).DataTable().columns.adjust();
    });

    // Clone header for search inputs
    $('#tbl_registrations_in_highschool thead tr').clone(true).appendTo('#tbl_registrations_in_highschool thead');
    $('#tbl_registrations_in_highschool thead tr:eq(1) th').each(function (i) {
        if ($(this).attr('searchable') != '1') {
            $(this).html('');
        } else {
            var title = $(this).text();
            $(this).html('<input type="text" class="form-control" placeholder="Search ' + title + '" />');

            $('input', this).on('keyup change', function () {
                if (tbl_registrations_in_highschool.column(i).search() !== this.value) {
                    tbl_registrations_in_highschool.column(i).search(this.value).draw();
                }
            });
        }
    });

    // Pending pay type table
    tbl_pending_pay_type_rec = $("#tbl_pending_pay_type_rec").DataTable({
        language: {
            'emptyTable': 'No pending applications found.'
        },
        dom: datatableDom,
        buttons: datatableButtons,
        ajax: $('#students-rec-config').data('pending-pay-type-url'),
        columns: [
            {
                'render': function (data, type, row, meta) {
                    return row.name + " <br>" + row.action;
                }
            },
            {
                'render': function (data, type, row, meta) {
                    return row.psid;
                }
            },
            {
                'render': function (data, type, row, meta) {
                    return row.pay_type;
                }
            },
            {
                'render': function (data, type, row, meta) {
                    return row.class_section;
                }
            },
            {
                'render': function (data, type, row, meta) {
                    return row.status;
                }
            }
        ]
    });

    function get_registrations_in_highschool() {
        tbl_registrations_in_highschool.destroy();

        tbl_registrations_in_highschool = $("#tbl_registrations_in_highschool").DataTable({
            ajax: '/highschool_admin/api/registration/?format=datatables&' + $('#frm_registration_term_filter').serialize(),
            serverSide: true,
            dom: datatableDom,
            buttons: datatableButtons,
            processing: true,
            orderCellsTop: true,
            fixedHeader: true,
            language: {
                'loadingRecords': '&nbsp;',
                'emptyTable': 'No students found for the selected term. Please select a different term'
            },
            lengthMenu: [30, 50, 100],
            order: [[0, 'desc']],
            columns: [
                {
                    'render': function (data, type, row, meta) {
                        return row.created_on;
                    }
                },
                {
                    'render': function (data, type, row, meta) {
                        return row.pay_type_pretty;
                    }
                },
                {
                    'render': function (data, type, row, meta) {
                        var consent_status = '';
                        if (row.has_signed_student_agreement == 'True') {
                            consent_status += '<span title="Student Agreement" class="badge badge-success">';
                        } else {
                            consent_status += '<span title="Student Agreement" class="badge badge-danger">';
                        }
                        consent_status += 'SA</span>&nbsp;&nbsp;';

                        return row.student.user.last_name + '<br>' + consent_status;
                    }
                },
                {
                    'render': function (data, type, row, meta) {
                        return row.student.user.first_name;
                    }
                },
                {
                    'render': function (data, type, row, meta) {
                        return row.class_section.course.name + ' ' + row.class_section.section_number + " " +
                            ' (' + row.class_section.course.credit_hours + ' credits)<br>' +
                            "<span class='text-muted'>" + row.class_section.course.title + '</span><br>' +
                            "<span class=''>" + "CRN " + row.class_section.class_number + "</span>";
                    }
                },
                {
                    'render': function (data, type, row, meta) {
                        var col = row.status_pretty;
                        if (row.changed_on !== null)
                            col += '<br>' + 'on ' + row.changed_on;
                        return col;
                    }
                },
                {
                    'render': function (data, type, row, meta) {
                        var hs = '';
                        if (row.reviewer === null) {
                            return hs;
                        }
                        hs += row.reviewer.user.last_name + ', ' + row.reviewer.user.first_name;
                        return hs;
                    }
                }
            ]
        });
    }

    function get_students_in_highschool() {
        tbl_in_highschool.destroy();

        tbl_in_highschool = $("#tbl_in_highschool").DataTable({
            language: {
                'emptyTable': 'No students found for the selected term. Please select a different term'
            },
            dom: datatableDom,
            buttons: datatableButtons,
            ajax: '/highschool_admin/api/students/?format=datatables&' + $('#frm_students_term_filter').serialize(),
            lengthMenu: [30, 50, 100],
            columns: [
                {
                    'width': '30%',
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
                        return row.username;
                    }
                },
                {
                    'width': '15%',
                    'render': function (data, type, row, meta) {
                        return row.graduation_year;
                    }
                },
                {
                    'width': '15%',
                    'render': function (data, type, row, meta) {
                        return "<a class='btn btn-sm btn-primary' href='" + row.details + "#classes'>View Details</a>";
                    }
                }
            ]
        });
    }

    function get_pending_rec() {
        tbl_pending_rec.destroy();

        tbl_pending_rec = $("#tbl_pending_rec").DataTable({
            language: {
                'emptyTable': 'No pending applications found.'
            },
            dom: datatableDom,
            buttons: datatableButtons,
            ajax: '/highschool_admin/api/pending-recommendations/?format=datatables',
            columns: [
                {
                    'render': function (data, type, row, meta) {
                        return row.name + " <br>" + row.action;
                    }
                },
                {
                    'render': function (data, type, row, meta) {
                        return row.psid;
                    }
                },
                {
                    'width': '15%',
                    'render': function (data, type, row, meta) {
                        return "<a class='btn btn-sm btn-primary' href='" + row.details + "'>Submit Rec.</a>";
                    }
                }
            ]
        });
    }

    get_pending_rec();
    get_students_in_highschool();
    get_registrations_in_highschool();

    $(document).on("change", "form#frm_registration_term_filter :input", function () {
        get_registrations_in_highschool();
    });

    $(document).on("change", "form#frm_students_term_filter :input", function () {
        get_students_in_highschool();
    });

    $(document).on('click', 'a.btn', function () {
        var src = $(this).attr('href');

        $("#details_src").attr('src', src);
        $('#details').modal('show');
        return false;
    });

    $('#details').on('hidden.bs.modal', function () {
        get_pending_rec();
    });
});
