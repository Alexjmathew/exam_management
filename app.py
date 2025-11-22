from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from functools import wraps
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
import json
import uuid
from datetime import datetime
import qrcode
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Firebase initialization
cred = credentials.Certificate('firebase_config.json')
firebase_admin.initialize_app(cred, {
    'storageBucket': 'your-project-id.appspot.com'
})

db = firestore.client()
bucket = storage.bucket()

# Role-based access control
ROLES = {
    'STUDENT': 'Student',
    'INVIGILATOR': 'Invigilator', 
    'EXAM_HEAD': 'Exam Head',
    'VALUATOR': 'Valuator',
    'DEVELOPER': 'Developer/Admin'
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_role):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user_role = session.get('user', {}).get('role')
            if user_role != required_role:
                return "Unauthorized", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Authentication Routes
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            # Firebase authentication
            user = auth.get_user_by_email(email)
            user_doc = db.collection('users').document(user.uid).get()
            
            if user_doc.exists:
                session['user'] = {
                    'uid': user.uid,
                    'email': user.email,
                    'role': user_doc.to_dict().get('role'),
                    'name': user_doc.to_dict().get('name')
                }
                return redirect(url_for('dashboard'))
            
        except Exception as e:
            return render_template('auth/login.html', error=str(e))
    
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        short_code = request.form.get('short_code', '')
        
        try:
            # Create Firebase user
            user = auth.create_user(email=email, password=password)
            
            # Store additional user data
            user_data = {
                'name': name,
                'email': email,
                'role': role,
                'short_code': short_code,
                'created_at': datetime.now()
            }
            
            db.collection('users').document(user.uid).set(user_data)
            
            # Additional role-specific data
            if role == 'STUDENT':
                student_data = {
                    'student_id': short_code,
                    'branch': request.form.get('branch'),
                    'semester': request.form.get('semester')
                }
                db.collection('students').document(user.uid).set(student_data)
            
            return redirect(url_for('login'))
            
        except Exception as e:
            return render_template('auth/register.html', error=str(e))
    
    return render_template('auth/register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Dashboard Routes
@app.route('/dashboard')
@login_required
def dashboard():
    user_role = session['user']['role']
    
    if user_role == 'STUDENT':
        return redirect(url_for('student_dashboard'))
    elif user_role == 'INVIGILATOR':
        return redirect(url_for('invigilator_dashboard'))
    elif user_role == 'EXAM_HEAD':
        return redirect(url_for('exam_head_dashboard'))
    elif user_role == 'VALUATOR':
        return redirect(url_for('valuator_dashboard'))
    else:
        return "Developer Dashboard - Under Construction"

# Student Routes
@app.route('/student/dashboard')
@role_required('STUDENT')
def student_dashboard():
    user_uid = session['user']['uid']
    
    # Get student data
    student_doc = db.collection('students').document(user_uid).get()
    student_data = student_doc.to_dict() if student_doc.exists else {}
    
    # Get upcoming exams
    exams_ref = db.collection('exams').where('status', '==', 'active')
    exams = [exam.to_dict() for exam in exams_ref.stream()]
    
    # Get hall tickets
    hall_tickets_ref = db.collection('hall_tickets').where('student_id', '==', user_uid)
    hall_tickets = [ticket.to_dict() for ticket in hall_tickets_ref.stream()]
    
    return render_template('student/student_dashboard.html', 
                         student=student_data, 
                         exams=exams, 
                         hall_tickets=hall_tickets)

@app.route('/student/hall-ticket/<exam_id>')
@role_required('STUDENT')
def download_hall_ticket(exam_id):
    user_uid = session['user']['uid']
    
    # Get hall ticket data
    hall_ticket_ref = db.collection('hall_tickets').where('student_id', '==', user_uid)\
                                                  .where('exam_id', '==', exam_id)\
                                                  .limit(1)
    hall_ticket_docs = list(hall_ticket_ref.stream())
    
    if not hall_ticket_docs:
        return "Hall ticket not found", 404
    
    hall_ticket = hall_ticket_docs[0].to_dict()
    
    # Generate PDF
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Add content to PDF
    p.drawString(100, 750, f"Hall Ticket - {hall_ticket['exam_name']}")
    p.drawString(100, 730, f"Student: {session['user']['name']}")
    p.drawString(100, 710, f"Student ID: {hall_ticket['student_code']}")
    p.drawString(100, 690, f"Room: {hall_ticket['room']}")
    p.drawString(100, 670, f"Seat: Row {hall_ticket['row']}, Seat {hall_ticket['seat']}")
    p.drawString(100, 650, f"Date: {hall_ticket['date']}")
    p.drawString(100, 630, f"Time: {hall_ticket['time']}")
    
    # Generate QR code
    qr_data = f"{hall_ticket['student_code']}|{exam_id}|{hall_ticket['room']}"
    qr = qrcode.make(qr_data)
    qr_buffer = BytesIO()
    qr.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    
    # Add QR code to PDF (simplified - in production, use proper image handling)
    p.drawString(100, 600, "QR Code: [Image would be here]")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, 
                    download_name=f"hall_ticket_{exam_id}.pdf",
                    mimetype='application/pdf')

# Exam Head Routes
@app.route('/exam-head/dashboard')
@role_required('EXAM_HEAD')
def exam_head_dashboard():
    # Get all exams
    exams_ref = db.collection('exams')
    exams = [{'id': exam.id, **exam.to_dict()} for exam in exams_ref.stream()]
    
    # Get malpractice reports
    malpractice_ref = db.collection('malpractice_reports').where('status', '==', 'pending')
    malpractice_reports = [report.to_dict() for report in malpractice_ref.stream()]
    
    return render_template('exam_head/exam_head_dashboard.html', 
                         exams=exams, 
                         malpractice_reports=malpractice_reports)

@app.route('/exam-head/create-exam', methods=['GET', 'POST'])
@role_required('EXAM_HEAD')
def create_exam():
    if request.method == 'POST':
        exam_data = {
            'name': request.form['name'],
            'date': request.form['date'],
            'time': request.form['time'],
            'subjects': request.form.getlist('subjects'),
            'total_seats': int(request.form['total_seats']),
            'status': 'draft',
            'created_by': session['user']['uid'],
            'created_at': datetime.now()
        }
        
        db.collection('exams').add(exam_data)
        return redirect(url_for('exam_head_dashboard'))
    
    return render_template('exam_head/create_exam.html')

@app.route('/exam-head/classroom-builder')
@role_required('EXAM_HEAD')
def classroom_builder():
    rooms_ref = db.collection('classrooms')
    rooms = [{'id': room.id, **room.to_dict()} for room in rooms_ref.stream()]
    return render_template('exam_head/classroom_builder.html', rooms=rooms)

@app.route('/exam-head/live-monitoring')
@role_required('EXAM_HEAD')
def live_monitoring():
    # Get all classrooms with seating status
    classrooms_ref = db.collection('classrooms')
    classrooms = []
    
    for classroom in classrooms_ref.stream():
        class_data = classroom.to_dict()
        class_data['id'] = classroom.id
        
        # Get attendance status
        attendance_ref = db.collection('attendance')\
                          .where('classroom_id', '==', classroom.id)\
                          .where('date', '==', datetime.now().date().isoformat())
        
        present_count = sum(1 for _ in attendance_ref.stream())
        class_data['present_count'] = present_count
        class_data['total_seats'] = class_data.get('rows', 0) * class_data.get('columns', 0)
        
        classrooms.append(class_data)
    
    return render_template('exam_head/live_monitoring.html', classrooms=classrooms)

# Invigilator Routes
@app.route('/invigilator/dashboard')
@role_required('INVIGILATOR')
def invigilator_dashboard():
    user_uid = session['user']['uid']
    
    # Get assigned classroom
    invigilator_ref = db.collection('invigilators').document(user_uid).get()
    invigilator_data = invigilator_ref.to_dict() if invigilator_ref.exists else {}
    classroom_id = invigilator_data.get('assigned_classroom')
    
    # Get classroom details
    classroom_data = {}
    if classroom_id:
        classroom_ref = db.collection('classrooms').document(classroom_id).get()
        classroom_data = classroom_ref.to_dict() if classroom_ref.exists else {}
    
    # Get students in classroom
    students = []
    if classroom_id:
        students_ref = db.collection('hall_tickets').where('classroom_id', '==', classroom_id)
        students = [student.to_dict() for student in students_ref.stream()]
    
    return render_template('invigilator/invigilator_dashboard.html',
                         classroom=classroom_data,
                         students=students)

@app.route('/invigilator/mark-attendance', methods=['POST'])
@role_required('INVIGILATOR')
def mark_attendance():
    student_id = request.json.get('student_id')
    classroom_id = request.json.get('classroom_id')
    status = request.json.get('status')
    
    attendance_data = {
        'student_id': student_id,
        'classroom_id': classroom_id,
        'status': status,
        'marked_by': session['user']['uid'],
        'timestamp': datetime.now(),
        'date': datetime.now().date().isoformat()
    }
    
    db.collection('attendance').add(attendance_data)
    return jsonify({'success': True})

@app.route('/invigilator/report-malpractice', methods=['POST'])
@role_required('INVIGILATOR')
def report_malpractice():
    student_id = request.form.get('student_id')
    description = request.form.get('description')
    severity = request.form.get('severity')
    
    # Handle file upload
    evidence_url = None
    if 'evidence' in request.files:
        file = request.files['evidence']
        if file.filename:
            blob = bucket.blob(f"malpractice_evidence/{uuid.uuid4()}_{file.filename}")
            blob.upload_from_file(file)
            evidence_url = blob.public_url
    
    malpractice_data = {
        'student_id': student_id,
        'reported_by': session['user']['uid'],
        'description': description,
        'severity': severity,
        'evidence_url': evidence_url,
        'status': 'pending',
        'reported_at': datetime.now()
    }
    
    db.collection('malpractice_reports').add(malpractice_data)
    return jsonify({'success': True})

# Valuator Routes
@app.route('/valuator/dashboard')
@role_required('VALUATOR')
def valuator_dashboard():
    # Get assigned answer sheets for evaluation
    answer_sheets_ref = db.collection('answer_sheets').where('status', '==', 'pending_evaluation')
    answer_sheets = [sheet.to_dict() for sheet in answer_sheets_ref.stream()]
    
    # Get pending approval results
    results_ref = db.collection('results').where('status', '==', 'pending_approval')
    pending_results = [result.to_dict() for result in results_ref.stream()]
    
    return render_template('valuator/valuator_dashboard.html',
                         answer_sheets=answer_sheets,
                         pending_results=pending_results)

if __name__ == '__main__':
    app.run(debug=True)
