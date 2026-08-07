import hashlib
import os
import cloudinary
import cloudinary.uploader
import pymongo
import streamlit as st

# --- ตั้งค่าการเชื่อมต่อฐานข้อมูลและ Cloudinary ---
# (ดึงค่าจาก st.secrets ตามที่ตั้งค่าไว้บน Streamlit Cloud)
MONGO_URI = st.secrets["MONGO_URI"]
client = pymongo.MongoClient(MONGO_URI)
db = client["worklog_db"]

user_auth_collection = db["users"]
profile_collection = db["profiles"]
log_collection = db["logs"]
visitor_collection = db["visitors"]

# ตั้งค่า Cloudinary
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
)


def hash_password(password):
  return hashlib.sha256(password.encode()).hexdigest()


@st.cache_data(ttl=300)
def get_cached_profile(username):
  profile = profile_collection.find_one({"author": username})
  if not profile:
    return {"bio": "ยังไม่ได้เขียนอธิบายตัวเอง...", "avatar": ""}
  return profile


# --- จัดการ Session State เบื้องต้น ---
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
if "username" not in st.session_state:
  st.session_state.username = ""

st.set_page_config(
    page_title="Work Log & Profile System", page_icon="📝", layout="wide"
)

# --- ระบบล็อกอิน / สมัครสมาชิก (หากยังไม่ได้เข้าสู่ระบบ) ---
if not st.session_state.logged_in:
  st.title("🔐 เข้าสู่ระบบ / สมัครสมาชิก")
  tab1, tab2 = st.tabs(["🔑 เข้าสู่ระบบ", "📝 สมัครสมาชิก"])

  with tab1:
    st.subheader("ยินดีต้อนรับกลับมา!")
    login_user = st.text_input("ชื่อผู้ใช้งาน", key="login_user")
    login_pass = st.text_input(
        "รหัสผ่าน", type="password", key="login_pass"
    )
    if st.button("🚀 เข้าสู่ระบบทันที", use_container_width=True):
      if not login_user or not login_pass:
        st.error("กรุณากรอกข้อมูลให้ครบถ้วน")
      else:
        user_record = user_auth_collection.find_one(
            {"username": login_user}
        )
        if user_record and user_record["password"] == hash_password(
            login_pass
        ):
          st.session_state.logged_in = True
          st.session_state.username = login_user
          st.success("เข้าสู่ระบบสำเร็จ!")
          st.rerun()
        else:
          st.error("❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

  with tab2:
    st.subheader("สร้างบัญชีใหม่")
    reg_user = st.text_input("กำหนดชื่อผู้ใช้งาน", key="reg_user")
    reg_pass = st.text_input("กำหนดรหัสผ่าน", type="password", key="reg_pass")
    if st.button("✨ ยืนยันการสมัครสมาชิก", use_container_width=True):
      if not reg_user or not reg_pass:
        st.error("กรุณากรอกข้อมูลให้ครบถ้วน")
      elif user_auth_collection.find_one({"username": reg_user}):
        st.error("❌ ชื่อผู้ใช้นี้ถูกใช้งานแล้ว กรุณาใช้ชื่ออื่น")
      else:
        # บันทึกข้อมูลผู้ใช้ใหม่
        user_auth_collection.insert_one({
            "username": reg_user,
            "password": hash_password(reg_pass),
        })
        # สร้างโปรไฟล์เริ่มต้น
        profile_collection.insert_one({
            "author": reg_user,
            "bio": "ยังไม่ได้เขียนอธิบายตัวเอง...",
            "avatar": "",
        })
        st.success(
            "🎉 สมัครสมาชิกสำเร็จ! สามารถสลับไปแท็บเข้าสู่ระบบได้เลย"
        )

  st.stop()  # หยุดการทำงานหน้าอื่นไว้จนกว่าจะล็อกอินสำเร็จ

# --- เมื่อเข้าสู่ระบบแล้ว (Main Application) ---
clean_user = st.session_state.username

st.sidebar.markdown(f"👤 **ผู้ใช้งาน:** {clean_user}")
if st.sidebar.button("🚪 ออกจากระบบ", use_container_width=True):
  st.session_state.logged_in = False
  st.session_state.username = ""
  st.rerun()

# --- ปุ่มรีสตาร์ทแอป (ล้างแคชทั้งหมดและโหลดหน้าใหม่) ---
st.sidebar.markdown("---")
if st.sidebar.button("🔄 รีสตาร์ทแอป (Clear Cache)", use_container_width=True):
  st.cache_data.clear()
  st.success("ล้างแคชและรีสตาร์ทระบบเรียบร้อย!")
  st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("#### 🎨 ตั้งค่าโปรไฟล์ส่วนตัว")
user_profile = get_cached_profile(clean_user)

with st.sidebar.form("profile_form"):
  new_bio = st.text_area("คำอธิบายสั้นๆ (Bio):", value=user_profile.get("bio", ""))
  avatar_file = st.file_uploader(
      "เปลี่ยนรูปโปรไฟล์", type=["png", "jpg", "jpeg"]
  )

  # เพิ่มระบบความปลอดภัย: ต้องกรอกรหัสผ่านปัจจุบันยืนยันก่อนแก้โปรไฟล์
  confirm_pass = st.text_input(
      "🔑 ยืนยันรหัสผ่านเพื่อบันทึก",
      type="password",
      placeholder="ใส่รหัสผ่านของคุณ",
  )

  save_profile = st.form_submit_button("💾 บันทึกโปรไฟล์", use_container_width=True)

  if save_profile:
    if not confirm_pass:
      st.error("กรุณากรอกรหัสผ่านเพื่อยืนยันการเปลี่ยนแปลง")
    else:
      # ตรวจสอบรหัสผ่านว่าถูกต้องจริงไหมก่อนให้บันทึก
      auth_check = user_auth_collection.find_one({"username": clean_user})
      if auth_check and auth_check["password"] == hash_password(confirm_pass):
        with st.spinner("กำลังอัปเดตข้อมูล..."):
          avatar_filename = user_profile.get("avatar", "")
          if avatar_file is not None:
            upload_avatar = cloudinary.uploader.upload(
                avatar_file, resource_type="image", folder="worklog_avatars"
            )
            avatar_filename = upload_avatar.get("secure_url")

          profile_collection.update_one(
              {"author": clean_user},
              {"$set": {"bio": new_bio, "avatar": avatar_filename}},
              upsert=True,
          )
          st.cache_data.clear()
        st.success("บันทึกโปรไฟล์สำเร็จ!")
        st.rerun()
      else:
        st.error("❌ รหัสผ่านไม่ถูกต้อง! ไม่อนุญาตให้แก้ไขโปรไฟล์")

# --- พื้นที่เนื้อหาหลักของแอป ---
st.title("📁 พอร์ตโฟลิโอและบันทึกงานของคุณ")
st.write(
    f"ยินดีต้อนรับคุณ **{clean_user}** เข้าสู่ระบบบันทึกรายงานการทำงาน"
    " และพื้นที่แชร์ผลงานอย่างปลอดภัย"
)

# แสดงข้อมูลโปรไฟล์ปัจจุบันในหน้าหลัก
col1, col2 = st.columns([1, 4])
with col1:
  if user_profile.get("avatar"):
    st.image(user_profile.get("avatar"), width=120)
  else:
    st.info("ยังไม่มีรูปโปรไฟล์")
with col2:
  st.markdown(f"### ผู้ใช้งาน: {clean_user}")
  st.markdown(f"**Bio:** {user_profile.get('bio', '')}")

st.markdown("---")
st.write("*(ระบบพร้อมใช้งาน คุณสามารถเขียนบันทึกงานหรือดูข้อมูลอื่นๆ ต่อได้)*")