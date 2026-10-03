/* Bulk per-student document upload (#6).
 * One request per chosen file, sequentially, with the result shown on the row:
 * a school sending hundreds of transcripts never builds one giant request, and
 * a rejected file does not stop the rest. */
(function () {
    var config = document.getElementById('student-docs-config');
    if (!config) { return; }

    function setStatus(row, ok, text) {
        var cell = row.querySelector('.doc-status');
        cell.textContent = text;
        cell.className = 'doc-status small ' + (ok ? 'text-success' : 'text-danger');
    }

    function uploadRow(row, documentType) {
        var input = row.querySelector('.doc-file');
        var data = new FormData();
        data.append('student', row.dataset.student);
        data.append('term', config.dataset.term);
        data.append('document_type', documentType);
        data.append('description', row.querySelector('.doc-note').value);
        data.append('media', input.files[0]);
        setStatus(row, true, 'Uploading…');
        return fetch(config.dataset.uploadUrl, {
            method: 'POST',
            body: data,
            headers: { 'X-CSRFToken': config.dataset.csrf, 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        }).then(function (r) {
            return r.json().catch(function () { return { status: 'error', message: 'Upload failed.' }; });
        }).then(function (resp) {
            var ok = resp.status === 'success';
            setStatus(row, ok, resp.message || (ok ? 'Uploaded.' : 'Upload failed.'));
            if (ok) { input.value = ''; }
        }).catch(function () {
            setStatus(row, false, 'Upload failed.');
        });
    }

    document.getElementById('btn_upload_selected').addEventListener('click', function () {
        var typeSelect = document.getElementById('id_document_type');
        var documentType = typeSelect.value;
        if (typeSelect.options.length > 1 && !documentType) {
            alert('Choose a document type first.');
            return;
        }
        var rows = Array.prototype.filter.call(
            document.querySelectorAll('#tbl_student_docs tbody tr[data-student]'),
            function (row) { var f = row.querySelector('.doc-file'); return f && f.files.length; });
        if (!rows.length) { alert('Choose at least one file.'); return; }

        var button = this;
        button.disabled = true;
        rows.reduce(function (chain, row) {
            return chain.then(function () { return uploadRow(row, documentType); });
        }, Promise.resolve()).then(function () { button.disabled = false; });
    });

    document.getElementById('id_student_filter').addEventListener('input', function () {
        var needle = this.value.toLowerCase();
        document.querySelectorAll('#tbl_student_docs tbody tr[data-student]').forEach(function (row) {
            var name = row.querySelector('.cv-name').textContent.toLowerCase();
            row.style.display = name.indexOf(needle) === -1 ? 'none' : '';
        });
    });
})();
