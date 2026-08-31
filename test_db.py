from config import db

cursor = db.cursor()

cursor.execute("SELECT DATABASE();")

result = cursor.fetchone()

print("Connected Database:", result)

cursor.close()
db.close()