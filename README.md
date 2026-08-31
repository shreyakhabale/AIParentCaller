# AI Student Absence Notification & Parent Voice Calling System

## Current project flow

College Login
-> College Dashboard
-> Create/manage teachers
-> Teacher Login
-> Teacher Dashboard
-> Student Management
-> Daily Attendance
-> Today's Absent Students
-> Parent Calling
-> Prepare Call
-> Call All Parents
-> Free Browser Voice Demo
-> Call History

## Free-cost calling mode

The project no longer depends on Twilio, Plivo, Exotel, or any paid calling API.

The **Call All Parents** feature prepares a personalized queue for today's absent students and uses the browser's Speech Synthesis API to speak the messages one by one. This is a working local demonstration and does not place real mobile-network calls.

## Gender-aware Marathi voice

The parent-call script supports gender-aware Marathi wording:

- Female: मुलगी / ती / तुमची / आली नाही
- Male: मुलगा / तो / तुमचा / आला नाही

The saved calling script can use placeholders such as:

- `{{student_name}}`
- `{{parent_name}}`
- `{{college_name}}`
- `{{child_word}}`
- `{{pronoun}}`
- `{{parent_child_word}}`
- `{{came_word}}`
- `{{did_not_come}}`

## Run

1. Open the project folder in VS Code.
2. Activate the virtual environment.
3. Install dependencies:

   `python -m pip install -r requirements.txt`

4. Make sure MySQL Server is running and the database `student_ai_system` exists.
5. Update the MySQL password in `app.py` and `config.py` if required.
6. Run:

   `python app.py`

7. Open:

   `http://127.0.0.1:5000/`

## Important

The project intentionally keeps the real phone-network calling part out of the free version. A real PSTN call requires a telecom/VoIP provider and normally incurs charges and/or verification requirements.
