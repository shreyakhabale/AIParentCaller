CREATE TEACHER FIX
==================

This version fixes the Create Teacher flow without adding Department/Class fields to the teacher form.

Flow:
College Login -> Create Teacher -> app automatically resolves the college's department and class -> INSERT teacher -> verify INSERT -> Teacher List.

If MySQL rejects the INSERT, the exact MySQL error is now shown in the page flash message and printed in the terminal. This prevents a silent HTTP 200 failure.

TEST:
1. Start app.py.
2. Login to the college account.
3. Open Create Teacher.
4. Fill Teacher Name, Email, Username (optional), Mobile, Password.
5. Click Create Teacher.
6. You should be redirected to Teacher List and see the new teacher.

IMPORTANT:
Do not add class_id or department_id inputs to create_teacher.html. They are resolved internally from the college's existing department -> class mapping.
