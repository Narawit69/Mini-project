from datetime import datetime
import os
import streamlit as st
from pymongo import MongoClient

# 1. เชื่อมต่อกับ MongoDB
mongo_uri = st.secrets["MONGO_URI"]
client = MongoClient(mongo_uri)
db = client["worklog_db"]
collection = db["logs"]
# เพิ่ม Collection สำหรับเก็บข้อมูลโปรไฟล์ (รูปโปรไฟล์ / Bio)
profile_collection = db["profiles"]

# 2. กำหนด Path สำหรับเก็บไฟล์
UPLOAD_DIR = "./data_volumes"
if not os.path.exists(UPLOAD_DIR):
  os.makedirs(UPLOAD_DIR)

# ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="My Daily Work Log", page_icon="💻", layout="wide")

st.title("💻 My Daily Work Log & Social Space")
st.write("ระบบบันทึกรายงานการทำงานประจำวัน และพื้นที่แชร์ผลงานร่วมกัน")

# --- แถบด้านข้าง (Sidebar): ระบบระบุตัวตนและตั้งค่าโปรไฟล์ ---
st.sidebar.header("🔐 ตั้งค่าผู้ใช้งาน")
current_user = st.sidebar.text_input("ระบุชื่อของคุณ:", value="")

if not current_user.strip():
  st.warning("⚠️ กรุณากรอกชื่อของคุณที่แถบด้านข้างซ้ายมือ เพื่อเริ่มต้นใช้งานระบบครับ")
  st.stop()

clean_user = current_user.strip()
st.sidebar.success(f"ใช้งานในนาม: **{clean_user}**")

# จัดการข้อมูลโปรไฟล์ในฐานข้อมูล
user_profile = profile_collection.find_one({"author": clean_user})
if not user_profile:
  # ถ้ายังไม่มีโปรไฟล์ สร้างค่าเริ่มต้นไว้
  user_profile = {"author": clean_user, "bio": "ยังไม่ได้เขียนอธิบายตัวเอง...", "avatar": ""}
  profile_collection.insert_one(user_profile)

st.sidebar.divider()
st.sidebar.subheader("🎨 แก้ไขโปรไฟล์ของคุณ")
with st.sidebar.form("profile_form"):
  new_bio = st.text_area("คำอธิบายสั้นๆ (Bio):", value=user_profile.get("bio", ""))
  avatar_file = st.file_uploader("อัปโหลดรูปโปรไฟล์", type=["png", "jpg", "jpeg"])
  save_profile = st.form_submit_button("บันทึกโปรไฟล์")

  if save_profile:
    avatar_filename = user_profile.get("avatar", "")
    if avatar_file is not None:
      avatar_filename = f"avatar_{clean_user}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{avatar_file.name}"
      avatar_path = os.path.join(UPLOAD_DIR, avatar_filename)
      with open(avatar_path, "wb") as f:
        f.write(avatar_file.getbuffer())
    
    profile_collection.update_one(
        {"author": clean_user},
        {"$set": {"bio": new_bio, "avatar": avatar_filename}},
        upsert=True
    )
    st.success("บันทึกโปรไฟล์สำเร็จ!")
    st.rerun()

st.sidebar.divider()
# เมนูเปลี่ยนหน้า
nav_mode = st.sidebar.radio("📌 เลือกโหมดการใช้งาน", ["📁 งานของฉัน & จัดการ", "🌐 เยี่ยมชมโปรไฟล์เพื่อนๆ"])

# ==========================================
# โหมดที่ 1: งานของฉัน & จัดการ (My Work Log)
# ==========================================
if nav_mode == "📁 งานของฉัน & จัดการ":
  st.header(f"📁 พอร์ตโฟลิโอและบันทึกงานของ: {clean_user}")
  
  # แสดงส่วนหัวโปรไฟล์ของตัวเอง
  col_p1, col_p2 = st.columns([1, 4])
  with col_p1:
    avatar_img = user_profile.get("avatar", "")
    if avatar_img and os.path.exists(os.path.join(UPLOAD_DIR, avatar_img)):
      st.image(os.path.join(UPLOAD_DIR, avatar_img), width=120)
    else:
      st.info("🖼️ ยังไม่มีรูปโปรไฟล์")
  with col_p2:
    st.write(f"**Bio:** {user_profile.get('bio', '-')}")

  st.divider()

  # ฟอร์มเพิ่มงานใหม่
  with st.form("worklog_form"):
    st.subheader("📝 เพิ่มบันทึกงานใหม่")
    log_date = st.date_input("วันที่ปฏิบัติงาน", datetime.today())
    title = st.text_input("หัวข้อเรื่อง / งานที่ทำ")
    category = st.selectbox(
        "หมวดหมู่งาน", ["Coding", "Meeting", "Debugging", "Learning", "Other"]
    )
    content = st.text_area("รายละเอียดการทำงาน")

    uploaded_file = st.file_uploader(
        "แนบไฟล์หลักฐาน (รูปภาพ/เอกสาร/วิดีโอ)", 
        type=["png", "jpg", "jpeg", "pdf", "mp4", "mov", "avi"]
    )

    submitted = st.form_submit_button("บันทึกข้อมูล")

    if submitted:
      if title and content:
        if "form_submitted" not in st.session_state:
          st.session_state.form_submitted = False

        if not st.session_state.form_submitted:
          st.session_state.form_submitted = True

          filename = ""
          if uploaded_file is not None:
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
            file_path = os.path.join(UPLOAD_DIR, filename)
            with open(file_path, "wb") as f:
              f.write(uploaded_file.getbuffer())

          log_data = {
              "author": clean_user,
              "date": str(log_date),
              "title": title,
              "category": category,
              "content": content,
              "attachment": filename,
              "comments": [],  # รองรับระบบคอมเมนต์
              "created_at": datetime.now(),
          }
          collection.insert_one(log_data)
          st.success("บันทึกข้อมูลสำเร็จเรียบร้อยแล้ว! 🎉")
          st.session_state.form_submitted = False
          st.rerun()
      else:
        st.warning("กรุณากรอกหัวข้อและรายละเอียดให้ครบถ้วนครับ")

  st.divider()
  st.subheader("📚 ประวัติงานของคุณ")
  user_logs = list(collection.find({"author": clean_user}).sort("created_at", -1))

  if len(user_logs) == 0:
    st.info("ยังไม่มีประวัติบันทึกงาน เริ่มเพิ่มข้อมูลกันเลย!")
  else:
    for log in user_logs:
      with st.expander(f"📌 [{log['category']}] {log['title']} ({log['date']})"):
        st.write(f"**รายละเอียด:** {log['content']}")
        
        if log.get("attachment"):
          st.write(f"📎 **ไฟล์แนบ:** {log['attachment']}")
          file_path = os.path.join(UPLOAD_DIR, log["attachment"])
          if os.path.exists(file_path):
            if log["attachment"].lower().endswith(("png", "jpg", "jpeg")):
              st.image(file_path, width=400)
            elif log["attachment"].lower().endswith(("mp4", "mov", "avi")):
              st.video(file_path)

        # แสดงรายการคอมเมนต์ที่มีคนมาฝากไว้
        comments = log.get("comments", [])
        if comments:
          st.markdown("---")
          st.markdown("💬 **ความคิดเห็นจากผู้เยี่ยมชม:**")
          for c in comments:
            st.markdown(f"- **{c['user']}:** {c['text']} <span style='color:gray; font-size:small;'>({c['time']})</span>", unsafe_allow_html=True)

        st.markdown("---")
        if st.button("🗑️ ลบบันทึกนี้", key=str(log["_id"])):
          collection.delete_one({"_id": log["_id"]})
          if log.get("attachment"):
            target_file = os.path.join(UPLOAD_DIR, log["attachment"])
            if os.path.exists(target_file):
              os.remove(target_file)
          st.success("ลบข้อมูลสำเร็จแล้ว!")
          st.rerun()

# ==========================================
# โหมดที่ 2: เยี่ยมชมโปรไฟล์เพื่อนๆ (Explore)
# ==========================================
elif nav_mode == "🌐 เยี่ยมชมโปรไฟล์เพื่อนๆ":
  st.header("🌐 หน้าสำรวจและเยี่ยมชมโปรไฟล์ผู้อื่น")
  st.write("เลือกดูโปรไฟล์และผลงานของเพื่อนๆ ในระบบ พร้อมส่งคอมเมนต์ให้กำลังใจได้ที่นี่ครับ!")

  # ดึงรายชื่อผู้ใช้งานทั้งหมดที่ไม่ซ้ำกันจากฐานข้อมูล
  all_authors = collection.distinct("author")
  # กรองชื่อตัวเองออก หรือจะเก็บไว้ก็ได้ (แต่เรามาส่องคนอื่น เลือกโชว์คนอื่น)
  other_authors = [a for a in all_authors if a.lower() != clean_user.lower()]

  if len(other_authors) == 0:
    st.info("ยังไม่มีผู้ใช้งานคนอื่นในระบบเลยครับ ลองชวนเพื่อนๆ มาใช้งานกันดูนะ!")
  else:
    selected_friend = st.selectbox("🔍 เลือกระบุชื่อเพื่อนที่คุณต้องการเยี่ยมชม:", other_authors)
    
    if selected_friend:
      st.divider()
      # ดึงข้อมูลโปรไฟล์ของเพื่อนคนนั้น
      friend_profile = profile_collection.find_one({"author": selected_friend}) or {}
      
      f_col1, f_col2 = st.columns([1, 4])
      with f_col1:
        f_avatar = friend_profile.get("avatar", "")
        if f_avatar and os.path.exists(os.path.join(UPLOAD_DIR, f_avatar)):
          st.image(os.path.join(UPLOAD_DIR, f_avatar), width=120)
        else:
          st.info("🖼️ ไม่มีรูปโปรไฟล์")
      with f_col2:
        st.subheader(f"👤 โปรไฟล์ของ: {selected_friend}")
        st.write(f"**Bio:** {friend_profile.get('bio', 'ยังไม่มีคำอธิบาย')}")

      st.divider()
      st.subheader(f"📚 ผลงานของ {selected_friend}")
      friend_logs = list(collection.find({"author": selected_friend}).sort("created_at", -1))

      if len(friend_logs) == 0:
        st.info(f"เพื่อนชื่อ '{selected_friend}' ยังไม่มีประวัติงานบันทึกไว้ครับ")
      else:
        for log in friend_logs:
          with st.expander(f"📌 [{log['category']}] {log['title']} ({log['date']})"):
            st.write(f"**รายละเอียด:** {log['content']}")
            
            if log.get("attachment"):
              st.write(f"📎 **ไฟล์แนบ:** {log['attachment']}")
              file_path = os.path.join(UPLOAD_DIR, log["attachment"])
              if os.path.exists(file_path):
                if log["attachment"].lower().endswith(("png", "jpg", "jpeg")):
                  st.image(file_path, width=400)
                elif log["attachment"].lower().endswith(("mp4", "mov", "avi")):
                  st.video(file_path)

            # แสดงคอมเมนต์เดิม
            comments = log.get("comments", [])
            st.markdown("---")
            st.markdown("💬 **ความคิดเห็นทั้งหมด:**")
            if comments:
              for c in comments:
                st.markdown(f"- **{c['user']}:** {c['text']} <span style='color:gray; font-size:small;'>({c['time']})</span>", unsafe_allow_html=True)
            else:
              st.caption("ยังไม่มีความคิดเห็น เป็นคนแรกที่คอมเมนต์เลยสิ!")

            # ฟอร์มฝากคอมเมนต์ (คนอื่นพิมพ์คอมเมนต์ได้ แต่ไม่มีสิทธิ์ลบโพสต์เด็ดขาด)
            with st.form(key=f"comment_form_{log['_id']}"):
              comment_text = st.text_input("💬 แสดงความคิดเห็น:")
              submit_comment = st.form_submit_button("ส่งคอมเมนต์")
              
              if submit_comment:
                if comment_text.strip():
                  new_comment = {
                      "user": clean_user,
                      "text": comment_text.strip(),
                      "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                  }
                  collection.update_one(
                      {"_id": log["_id"]},
                      {"$push": {"comments": new_comment}}
                  )
                  st.success("ส่งคอมเมนต์เรียบร้อยแล้ว! 🚀")
                  st.rerun()
                else:
                  st.warning("กรุณาพิมพ์ข้อความคอมเมนต์ก่อนส่งครับ")
            
            st.caption("🔒 (โหมดเยี่ยมชม: คุณสามารถดูและคอมเมนต์ได้เท่านั้น ไม่สามารถแก้ไขหรือลบโพสต์นี้ได้)")