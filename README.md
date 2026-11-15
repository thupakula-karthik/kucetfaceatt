# Student Attendance and Risk Analysis System Using Facial Recognition

A Flask application starter for student registration, browser-camera face recognition,
class-session attendance, attendance percentage monitoring and Excel exports.

## Important deployment notes

- Browser camera access requires HTTPS. Render provides HTTPS on its hosted URL.
- Face images and attendance records are sensitive student information. Use consent,
  restrict repository access, and do not upload real student photos or database files
  to a public GitHub repository.
- This starter stores one captured face image per student in SQLite. For a real
  institutional deployment, add authenticated roles, access controls, retention rules,
  backups and an institution-approved privacy process.
- Render's persistent disk is configured in `render.yaml`. Persistent disks may require
  a paid Render plan. Confirm current plan availability and pricing in Render.
- A public demo should not be used for real student records without security review.

## Run locally

1. Install Python 3.11.
2. Open a terminal in this folder.
3. Create a virtual environment:
   `python -m venv .venv`
4. Activate it on Windows:
   `.venv\\Scripts\\activate`
5. Install packages:
   `pip install -r requirements.txt`
6. Download the official OpenCV Zoo models:
   `python download_models.py`
7. Start the app:
   `python app.py`
8. Open `http://127.0.0.1:5000`.

## Deploy to Render

1. Create a private GitHub repository.
2. Add the project files, excluding `attendance.db`, real face photos and secrets.
3. Push the repository to GitHub.
4. In Render, create a new Blueprint and select the repository.
5. Review the `render.yaml` configuration and deploy.
6. Open the HTTPS Render URL and allow camera access in the browser.

## Pages

- `/` Home
- `/register` Student registration and face capture
- `/teacher` Create class sessions and export attendance
- `/start/<session_id>` Browser-camera attendance
- `/student` Student attendance lookup
- `/parent` Redirects to student lookup in this starter version
- `/health` Health check

## Attendance recognition

YuNet detects a face in the browser-captured image. SFace extracts facial features
and compares them with the registered face image. The cosine similarity threshold
is set to 0.363 as an initial setting; test and calibrate it carefully for your
camera, lighting and environment. Recognition is not guaranteed to be error-free.
"# kucetatt" 
