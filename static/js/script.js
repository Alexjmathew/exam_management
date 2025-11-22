// Global JavaScript functions for the exam management system

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Mark attendance functionality
    const markAttendanceButtons = document.querySelectorAll('.mark-attendance');
    markAttendanceButtons.forEach(button => {
        button.addEventListener('click', function() {
            const studentId = this.dataset.studentId;
            const classroomId = this.dataset.classroomId;
            const status = this.dataset.status;
            
            fetch('/invigilator/mark-attendance', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    student_id: studentId,
                    classroom_id: classroomId,
                    status: status
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update UI
                    this.innerHTML = status === 'present' ? 
                        '<i class="fas fa-check"></i> Present' : 
                        '<i class="fas fa-times"></i> Absent';
                    this.classList.toggle('btn-success', status === 'present');
                    this.classList.toggle('btn-danger', status === 'absent');
                    
                    // Show success message
                    showAlert('Attendance marked successfully!', 'success');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('Error marking attendance', 'danger');
            });
        });
    });

    // Malpractice reporting
    const reportMalpracticeForm = document.getElementById('reportMalpracticeForm');
    if (reportMalpracticeForm) {
        reportMalpracticeForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            
            fetch('/invigilator/report-malpractice', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showAlert('Malpractice reported successfully!', 'success');
                    this.reset();
                    
                    // Close modal if exists
                    const modal = bootstrap.Modal.getInstance(document.getElementById('malpracticeModal'));
                    if (modal) modal.hide();
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('Error reporting malpractice', 'danger');
            });
        });
    }
});

// Utility function to show alerts
function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.querySelector('.container').insertBefore(alertDiv, document.querySelector('.container').firstChild);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.parentNode.removeChild(alertDiv);
        }
    }, 5000);
}

// Classroom builder functionality
function initializeClassroomBuilder() {
    const gridContainer = document.getElementById('seatingGrid');
    if (!gridContainer) return;
    
    const rows = parseInt(gridContainer.dataset.rows) || 5;
    const cols = parseInt(gridContainer.dataset.cols) || 5;
    
    // Create seating grid
    gridContainer.style.gridTemplateColumns = `repeat(${cols}, 40px)`;
    
    for (let i = 0; i < rows; i++) {
        for (let j = 0; j < cols; j++) {
            const seat = document.createElement('div');
            seat.className = 'seat available';
            seat.dataset.row = i + 1;
            seat.dataset.col = j + 1;
            seat.textContent = `${i + 1}-${j + 1}`;
            
            seat.addEventListener('click', function() {
                // Toggle seat status for demo purposes
                const statuses = ['available', 'occupied', 'blocked'];
                const currentStatus = this.className.replace('seat ', '');
                const nextStatus = statuses[(statuses.indexOf(currentStatus) + 1) % statuses.length];
                
                this.className = `seat ${nextStatus}`;
            });
            
            gridContainer.appendChild(seat);
        }
    }
}

// Initialize when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeClassroomBuilder);
} else {
    initializeClassroomBuilder();
}
