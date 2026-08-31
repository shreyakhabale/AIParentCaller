# AI-Based Student Absence Notification & Parent Voice Calling System

## College + Teacher + Android Login Architecture

### College Registration
A new college creates an account from `/college_register`.
The system keeps the internal numeric `college_id` and automatically creates a separate user-facing login ID:

- `college_id` = College ID and database primary key (1, 2, 3, ...)
- `college_login_id` = compatibility field storing the same numeric College ID

Existing colleges use their existing numeric `college_id` as the College ID.

### College Web Login
College login requires:

1. College ID
2. Username
3. Password

After successful login, the session stores the college ID and all college-management screens continue to filter data by the logged-in college.

### Teacher Login
Teacher login also requires:

1. College ID
2. Teacher Username
3. Password

The teacher is looked up through the college relationship, so the same username in another college cannot be used with the wrong College ID.

### Android App
The Android companion now has:

1. Flask Server URL
2. College ID
3. College Username
4. College Password
5. College Login

After login it shows:

- College information
- Pending Calls count/list
- Refresh Pending Calls
- Start Automatic SIM Calling
- Stop Calling
- Logout

The Android app receives a signed access token after login and uses that token for the calling queue. The old bridge-token method remains available for compatibility.

## Existing Project Features Preserved

- College registration/profile
- Teacher management
- Student management
- Daily attendance / absence marking
- Parent calling queue
- Call history
- Voice settings
- Local AI API
- Android SIM calling bridge

## Calling / Voice Limitation

The free Android SIM bridge can place and track normal cellular calls. A standard Android cellular call does not provide a supported third-party API for injecting arbitrary local AI audio into the call uplink or capturing the parent's speech from the cellular call.

Therefore:
- The calling queue and SIM calling workflow are implemented.
- Call status and duration can be recorded.
- Local Qwen + faster-whisper can be used for local voice processing outside the cellular call path.
- True live two-way AI conversation over a normal phone call requires a supported telephony/media solution or dedicated telephony hardware.

## Network

The Android phone must be able to reach the Flask server. For same-network testing, use the laptop's LAN IP, for example:

`http://192.168.1.10:5000`

Do not use `127.0.0.1` on the Android phone because that points to the phone itself.

## Run

Start the Flask application as usual:

`python app.py`

Then:

1. Open College Registration.
2. Create a college account.
3. Save the generated College ID.
4. Login with College ID + Username + Password.
5. Create teacher accounts.
6. Teacher logs in with College ID + Username + Password.
7. Manage students and attendance.
8. Queue absent-student parent calls.
9. Login to the Android companion with the same college credentials.
10. Refresh pending calls and start the SIM calling worker.
