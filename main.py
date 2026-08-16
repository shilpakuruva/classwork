from  flask import Flask, render_template, request,session,jsonify,send_from_directory,redirect
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField,SelectField
from wtforms.validators import DataRequired, Length,Email
import pymysql
from werkzeug.utils import secure_filename
from datetime import date
import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
conn=pymysql.connect(host='localhost',user='root',password='Root#DB12345',db='projectclass')
UPLOAD_FOLDER = "uploads"
app = Flask(__name__)

cursor=conn.cursor()
app.config['SECRET_KEY'] = 'yyyxxyyy'
class loginForm(FlaskForm):

    email = StringField('Email',validators=[DataRequired(message="Please enter valid mail ."),Length(1,64),Email()])
    year = SelectField(
        "Year",
        choices=[
            ('1', '1st Year'),
            ('2', '2nd Year'),
            ('3', '3rd Year'),
            ('4', '4th Year')
        ]
    )


    section = SelectField(
        "Section",
        choices=[
            ('A', 'A'),
            ('B', 'B'),
            ('C', 'C'),
            ('D', 'D'),
            ('E', 'E')
        ]
    )

    submit = SubmitField('Login')
def create_session_notifications(subject_id, session_id):

    year = session.get("year")
    section = session.get("section")

    if year is None or section is None:
        return

    # Get subject name AND actual session number
    cursor.execute(
        """
        SELECT name
        FROM subjects
        WHERE id=%s
        """,
        (subject_id,)
    )

    subject_row = cursor.fetchone()

    if not subject_row:
        return

    subject_name = subject_row[0]

    # Get students from same year and section
    cursor.execute(
        """
        SELECT email
        FROM login
        WHERE year=%s
        AND section=%s
        """,
        (year, section)
    )

    students = cursor.fetchall()

    # Get the actual session number
    cursor.execute(
        """
        SELECT session
        FROM sectiond
        WHERE id=%s
        """,
        (session_id,)
    )

    session_row = cursor.fetchone()

    if not session_row:
        return

    actual_session_number = session_row[0]

    # Create notification for every student
    for student in students:

        email = student[0]

        cursor.execute(
            """
            INSERT INTO notifications
            (
                student_email,
                year,
                section,
                subject_id,
                session_id,
                notification_type,
                title,
                message
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                'SESSION_ADDED',
                %s,
                %s
            )
            """,
            (
                email,
                year,
                section,
                subject_id,
                session_id,
                "New Session Created",
                f"New Session {actual_session_number} has been added to {subject_name}."
            )
        )

    conn.commit()
@app.route('/',methods=['GET','POST'])
def login():

    login=loginForm()
    if login.validate_on_submit():
        givenmail = login.email.data
        givenyear = login.year.data
        givensection = login.section.data
        try:
         cursor.execute("""
                       SELECT email, power
                       FROM login
                       WHERE email = %s
                                 AND year = %s
                         AND section =%s
                       """,
                       (givenmail, givenyear, givensection))
         row=cursor.fetchone()
        except Exception as e:
            return render_template('login.html', form=login, istried=1)
        if row:
            actualmail=row[0]
            if givenmail==actualmail:
                print(row[1])
                cursor.execute("select name from subjects ")
                subjects = cursor.fetchall()
                print(subjects)
                if row[1]==1:

                    if row[1] == 1:
                        session["power"] = 1
                        session["year"] = givenyear
                        session["section"] = givensection
                        session["email"] = givenmail

                        return redirect("/allsubjects")

                else:


                    session["power"] = 0
                    session["year"] = givenyear
                    session["section"] = givensection
                    session["email"] = givenmail

                    return redirect("/allsubjects")

        else:
            return render_template('login.html',form=login,istried=1)
    return render_template('login.html',form=login,istried=0)
@app.route("/allsubjects",methods=["GET","POST"])
def all_subjects():
    cursor.execute("select name from subjects ")
    subjects = cursor.fetchall()
    return render_template("crcm.html", subjects=subjects)
@app.route('/subject',methods=['GET','POST'])
def subject(): 
    if session.get("power") == None:
       return redirect("/")
    if request.method == "POST":
            subject_id = request.form.get("subject_id")
            session["subject"] = subject_id


    else:  # GET

        subject_id = request.args.get("subject_id")

        if subject_id:

            session["subject"] = subject_id

        else:

            subject_id = session.get("subject")
    if subject_id == None:
        return redirect("/")
    print("subject id ",subject_id)
    cursor.execute("select name from subjects where id = %s",(subject_id,))
    srow=cursor.fetchone()
    subject_name=srow[0]
    cursor.execute("""
                   SELECT s.id,
                          s.session,
                          s.data,
                          s.topic_covered,
                          s.homework,

                          t.original_name,
                          t.stored_name,

                          h.original_name,
                          h.stored_name

                   FROM sectiond s

                            LEFT JOIN session_attachments t
                                      ON s.id = t.sessionid
                                          AND t.attachment_type = 'topic'

                            LEFT JOIN session_attachments h
                                      ON s.id = h.sessionid
                                          AND h.attachment_type = 'homework'

                   WHERE s.subjectid = %s

                   ORDER BY s.session
                   """, (subject_id,))
    rows = cursor.fetchall()
    latest_session = rows[-1][0] if rows else None
    if session.get("power") == 1:
        can_edit = True
    else:
        can_edit = False

    return render_template(
        "subject.html",
        rows=rows,
        subject_id=subject_id,
        latest_session=latest_session,
        subject_name=subject_name,
        can_edit=can_edit)
@app.route("/update_session",methods=["POST"])
def update_session():
    if session.get("power") == 0 or session.get("power")==None:
        return redirect("/")
    sessionid = request.form["id"]
    topic = request.form["topic"]
    homework = request.form["homework"]

    cursor.execute("""
                   UPDATE sectiond
                   SET topic_covered=%s,
                       homework=%s
                   WHERE id = %s
                   """, (topic, homework, sessionid))

    # ---------- Topic Attachment ----------
    if "topicFile" in request.files:

        file = request.files["topicFile"]

        if file.filename != "":

            original_name = file.filename
            extension = os.path.splitext(file.filename)[1]
            stored_name = str(uuid.uuid4()) + extension

            file.save(os.path.join(UPLOAD_FOLDER, stored_name))

            cursor.execute("""
                           SELECT id
                           FROM session_attachments
                           WHERE sessionid = %s
                             AND attachment_type = 'topic'
                           """, (sessionid,))

            if cursor.fetchone():

                cursor.execute("""
                               UPDATE session_attachments
                               SET original_name=%s,
                                   stored_name=%s
                               WHERE sessionid = %s
                                 AND attachment_type = 'topic'
                               """, (original_name, stored_name, sessionid))

            else:

                cursor.execute("""
                               INSERT INTO session_attachments
                                   (sessionid, attachment_type, original_name, stored_name)
                               VALUES (%s, 'topic', %s, %s)
                               """, (sessionid, original_name, stored_name))

    # ---------- Homework Attachment ----------
    if "homeworkFile" in request.files:

        file = request.files["homeworkFile"]

        if file.filename != "":

            original_name = file.filename
            extension = os.path.splitext(file.filename)[1]
            stored_name = str(uuid.uuid4()) + extension

            file.save(os.path.join(UPLOAD_FOLDER, stored_name))

            cursor.execute("""
                           SELECT id
                           FROM session_attachments
                           WHERE sessionid = %s
                             AND attachment_type = 'homework'
                           """, (sessionid,))

            if cursor.fetchone():

                cursor.execute("""
                               UPDATE session_attachments
                               SET original_name=%s,
                                   stored_name=%s
                               WHERE sessionid = %s
                                 AND attachment_type = 'homework'
                               """, (original_name, stored_name, sessionid))

            else:

                cursor.execute("""
                               INSERT INTO session_attachments
                                   (sessionid, attachment_type, original_name, stored_name)
                               VALUES (%s, 'homework', %s, %s)
                               """, (sessionid, original_name, stored_name))

    conn.commit()

    return jsonify({
        "message": "Updated Successfully"
    })
@app.route("/download/<filename>")
def download(filename):
    if session.get("power") == None:
        return redirect("/")
    return send_from_directory(
        UPLOAD_FOLDER,
        filename,
        as_attachment=False   # Opens in browser if possible
    )
@app.route("/addsession", methods=["POST"])
def addsession():

    if session.get("power") == 0 or session.get("power") is None:
        return redirect("/")

    subject_id = request.form["subject_id"]

    # Find the last session number for this subject
    cursor.execute("""
        SELECT MAX(session)
        FROM sectiond
        WHERE subjectid=%s
    """, (subject_id,))

    row = cursor.fetchone()

    if row[0] is None:
        next_session = 1
    else:
        next_session = row[0] + 1

    # Insert new session
    cursor.execute("""
        INSERT INTO sectiond
        (
            subjectid,
            session,
            data,
            topic_covered,
            homework
        )
        VALUES
        (
            %s,
            %s,
            %s,
            '',
            ''
        )
    """, (
        subject_id,
        next_session,
        date.today()
    ))

    # Get newly created sectiond ID
    session_id = cursor.lastrowid

    conn.commit()

    # Create notifications for students
    create_session_notifications(
        subject_id,
        session_id
    )

    return redirect("/subject")

@app.route("/delete_session", methods=["POST", "GET"])
def delete_session():

    if session.get("power") == 0 or session.get("power") is None:
        return redirect("/")

    data = request.get_json()

    sessionid = data["id"]

    # Delete notifications related to this session
    cursor.execute(
        """
        DELETE FROM notifications
        WHERE session_id=%s
        """,
        (sessionid,)
    )

    # Delete attachments
    cursor.execute(
        """
        DELETE FROM session_attachments
        WHERE sessionid=%s
        """,
        (sessionid,)
    )

    # Delete session
    cursor.execute(
        """
        DELETE FROM sectiond
        WHERE id=%s
        """,
        (sessionid,)
    )

    conn.commit()

    return jsonify({
        "message": "Session Deleted Successfully"
    })
@app.route("/delete_attachment", methods=["POST"])
def delete_attachment():

    if session.get("power") != 1:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.get_json()

    sessionid = data["sessionid"]
    attachment_type = data["type"]

    cursor.execute("""
        SELECT stored_name
        FROM session_attachments
        WHERE sessionid=%s
        AND attachment_type=%s
    """, (sessionid, attachment_type))

    row = cursor.fetchone()

    if not row:
        return jsonify({"message": "Attachment not found"})

    stored_name = row[0]

    filepath = os.path.join(UPLOAD_FOLDER, stored_name)

    if os.path.exists(filepath):
        os.remove(filepath)

    cursor.execute("""
        DELETE FROM session_attachments
        WHERE sessionid=%s
        AND attachment_type=%s
    """, (sessionid, attachment_type))

    conn.commit()

    return jsonify({
        "message": "Attachment Deleted Successfully"
    })
@app.route("/notifications", methods=["GET"])
def get_notifications():

    if session.get("power") is None:
        return jsonify({
            "success": False,
            "message": "Not logged in"
        }), 401

    email = session.get("email")

    # Your current login code does not store email,
    # so get it from the login form/session if available.
    if not email:
        return jsonify({
            "success": False,
            "message": "Email not found"
        }), 401

    cursor.execute(
        """
        SELECT
            id,
            subject_id,
            session_id,
            notification_type,
            title,
            message,
            is_read,
            created_at
        FROM notifications
        WHERE student_email=%s
        ORDER BY created_at DESC
        """,
        (email,)
    )

    rows = cursor.fetchall()

    notifications = []

    for row in rows:

        notifications.append({
            "id": row[0],
            "subject_id": row[1],
            "session_id": row[2],
            "notification_type": row[3],
            "title": row[4],
            "message": row[5],
            "is_read": row[6],
            "created_at": str(row[7])
        })

    return jsonify({
        "success": True,
        "notifications": notifications
    })


@app.route("/notifications/count")
def notification_count():

    if session.get("power") is None:
        return jsonify({
            "count": 0
        })

    email = session.get("email")

    if not email:
        return jsonify({
            "count": 0
        })

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM notifications
        WHERE student_email=%s
        AND is_read=0
        """,
        (email,)
    )

    count = cursor.fetchone()[0]

    return jsonify({
        "count": count
    })


@app.route("/notifications/read/<int:notification_id>", methods=["POST"])
def mark_notification_read(notification_id):

    if session.get("power") is None:
        return jsonify({
            "success": False
        }), 401

    email = session.get("email")

    if not email:
        return jsonify({
            "success": False
        }), 401

    cursor.execute(
        """
        UPDATE notifications
        SET is_read=1
        WHERE id=%s
        AND student_email=%s
        """,
        (
            notification_id,
            email
        )
    )

    conn.commit()

    return jsonify({
        "success": True
    })
@app.route("/logout")
def logout():
    session.clear()      # Removes all session data
    return redirect("/")
if __name__ == '__main__':
    app.run(host="0.0.0.0",port=8080,debug=True)