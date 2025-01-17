document.addEventListener('DOMContentLoaded', function() {
    var roleSelect = document.getElementById('role');
    var doctorInfo = document.getElementById('teacher-info');

    roleSelect.addEventListener('change', function() {
        if (roleSelect.value === 'teacher') {
            doctorInfo.style.display = 'block';
        } else {
            doctorInfo.style.display = 'none';
        }
    });
});
