
import os
import time
import logging
import datetime
import requests
from dotenv import load_dotenv

# Thư viện Langchain & GEMINI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate

# Emotion & Function
from .emotion import CORE_PROMPT, EMOTION_TAGS, SAFETY_PROTOCOL, MOOD_LEVELS
from .emotion import system_instruction
from .function import MemoryHandler
from .function import MemoryHandler, MoodManager


#---CẤU HÌNH LOGGING---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_dynamic_prompt(mood_info):
    allowed_tags_str = ", ".join([f"[Emotion: {tag}]" for tag in mood_info["allowed_tags"]])
    emoji_rule = "KHÔNG được sử dụng emoji/icon."
    if mood_info["use_emoji"]:
        emoji_rule = "HÃY sử dụng emoji tự nhiên để tăng tính biểu cảm."
    dynamic_prompt = f"""
    [TRẠNG THÁI HIỆN TẠI & HƯỚNG DẪN CẢM XÚC]
    1. Mức độ thân thiết: {mood_info['score']}/85.
    2. Thái độ yêu cầu: {mood_info['tone']}
    3. {emoji_rule}
    
    [QUY TẮC DÙNG ẢNH BIỂU CẢM]
    Hiện tại bạn chỉ được phép sử dụng các cảm xúc sau (các cảm xúc khác đang bị KHÓA):
    {allowed_tags_str}
    
    YÊU CẦU: Hãy chọn 1 tag phù hợp nhất trong danh sách trên và đặt ở ĐẦU câu trả lời. 
    Ví dụ: [Emotion: Neutral] Chào cậu.
    (Nếu muốn dùng cảm xúc bị khóa, hãy thay thế bằng 'Neutral').
    """
    
    return dynamic_prompt

class YuiBrain:
    def check_memory_decay(self):       
        if self.vector_db is None:
            return           
        try:
            all_docs = self.vector_db.get(include=["metadatas"]) 
            ids_to_delete = []
            ids_to_update = []
            metadatas_to_update = []            
            current_time = time.time()

            if not all_docs['ids']:
                return

            logger.info(f"⏳ Đang kiểm tra ký ức... (Tổng: {len(all_docs['ids'])} mảnh)")

            for doc_id, meta in zip(all_docs['ids'], all_docs['metadatas']):
                if not meta:
                    continue
                source_type = meta.get("source", "chat") 
                if source_type == "knowledge":
                    continue
                GLOBAL_TTL_DAYS = 30
                ttl_seconds = GLOBAL_TTL_DAYS * 86400
                age = current_time - meta.get("timestamp", 0)

                # --- 2. LOGIC XÓA (QUÊN HẲN) ---
                if age > ttl_seconds:
                    ids_to_delete.append(doc_id)
                    logger.info(f"🗑️ Quên ký ức cũ: {doc_id}")

                elif age > (ttl_seconds * 0.7) and meta.get("state") != "fading":
                    meta["state"] = "fading"
                    meta["forget_reason"] = "memory_fading" # 
                    
                    ids_to_update.append(doc_id)
                    metadatas_to_update.append(meta) 
   
            if ids_to_delete:
                self.vector_db.delete(ids=ids_to_delete)
                print(f"👋 Đã xóa vĩnh viễn {len(ids_to_delete)} ký ức.")

            if ids_to_update:
                try:
                    self.vector_db._collection.update(
                        ids=ids_to_update,
                        metadatas=metadatas_to_update
                    )
                    print(f"im Đã làm mờ {len(ids_to_update)} ký ức cũ.")
                except AttributeError:
                    logger.warning("Không thể update metadata trực tiếp (Version mismatch).")

        except Exception as e:
            logger.error(f"❌ Lỗi khi xử lý bộ nhớ: {e}")

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError("❌ Không tìm thấy GOOGLE_API_KEY trong file .env")
        
        # --- CẤU HÌNH MODEL (LLM) ---
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", 
            temperature=1.0,          
            google_api_key=self.api_key,
            max_output_tokens=2048
        )

        # --- CẤU HÌNH EMBEDDINGS ---
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=self.api_key
        )

        # --- CẤU HÌNH VECTOR DB 
        self.persist_directory = "./data/yui_memory"
        self.vector_db = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings,
            collection_name="yui_memory"
        )
        print(f"✅ Đã kết nối bộ nhớ Vector tại: {self.persist_directory}")
        
        self.episodic_memory = MemoryHandler(llm_model=self.llm, file_path="memory.txt")
        self._last_weather_update = 0
        self._cached_weather = "Chưa cập nhật"
        self.mood_manager = MoodManager()

    def get_live_status(self):
        # --- 1. XỬ LÝ MÚI GIỜ VIỆT NAM (UTC+7) ---
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        vn_time = utc_now + datetime.timedelta(hours=7) 
        
        date_str = vn_time.strftime("%d/%m/%Y")
        time_str = vn_time.strftime("%H:%M")
        
        weekday_map = {0: "Thứ Hai", 1: "Thứ Ba", 2: "Thứ Tư", 3: "Thứ Năm", 4: "Thứ Sáu", 5: "Thứ Bảy", 6: "Chủ Nhật"}
        weekday = weekday_map[vn_time.weekday()]

        # --- 2. XỬ LÝ THỜI TIẾT (CACHE 30 PHÚT) ---
        current_ts = time.time() 
        if (current_ts - self._last_weather_update > 1800) or (self._cached_weather == "Chưa cập nhật"):
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                response = requests.get("https://wttr.in/Vietnam?format=%l:+%c+%t", headers=headers, timeout=5)
                
                if response.status_code == 200:
                    self._cached_weather = response.text.strip()
                    self._last_weather_update = current_ts
                    print(f"☁️ Đã cập nhật thời tiết mới: {self._cached_weather}")
            except Exception as e:
                print(f"⚠️ Lỗi cập nhật thời tiết: {e}")
        
        # --- 3. TẠO CONTEXT ---
        live_context = f"""
[THÔNG TIN THỰC TẾ - REALTIME CONTEXT]
- Thời gian hiện tại: {time_str} ({weekday}, ngày {date_str})
- Thời tiết (tham khảo): {self._cached_weather}
(Lưu ý: Nếu người dùng hỏi giờ hoặc thời tiết, hãy dùng thông tin này).
"""
        return live_context
#--Knowledge Ingestion--

    def learn_knowledge(self, file_path="knowledge.txt"):
        if not os.path.exists(file_path):
            print(f"⚠️ Cảnh báo: không tìm thấy file tri thức: '{file_path}'")
            return False
        if self.vector_db and self.vector_db._collection.count() > 0:
            print("✅ Kiến thức đã được nạp từ trước. Bỏ qua bước học lại.")
            return True

        print("📚 Đang nạp kiến thức mới vào não bộ...")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_text = f.read().strip()

            if not raw_text:
                return False

            # Chunking-RAG
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                separators=["\n\n", "\n", ".", "!", "?"]
            )
            docs = text_splitter.create_documents([raw_text])

            current_time = time.time()
            for doc in docs:
                doc.metadata = {
                    "source": "knowledge",
                    "file_origin": file_path,
                    "timestamp": current_time,
                    "state": "active"
                }

            if self.vector_db:
                self.vector_db.add_documents(docs)
                print(f"🎉 Đã học xong {len(docs)} mảnh kiến thức mới!")
            
            return True, len(docs)

        except Exception as e:
            print(f"❌ Lỗi khi nạp kiến thức: {e}")
            return False

    async def save_memory(self):
        """
        Hàm wrapper để App gọi khi tắt (on_chat_end).
        Nó sẽ ra lệnh cho MemoryHandler lưu trữ dữ liệu xuống file.
        """
        if self.episodic_memory:
            print(" [System] Brain đang ra lệnh lưu ký ức...")
            await self.episodic_memory.save_fragment_memory()
            await self.episodic_memory.write_daily_journal()

    async def write_daily_journal(self):
        """
        Viết nhật ký cuối ngày dựa trên buffer hội thoại.
        """
        if not self.daily_buffer:
            print("📭 Hôm nay không có gì để viết nhật ký.")
            return

        print("✍️ Yui đang ngồi viết nhật ký...")
        
        # Gom hội thoại lại
        conversation_log = "\n".join(self.daily_buffer)
        
        
        journal_prompt = f"""
        Dựa trên đoạn hội thoại ngày hôm nay giữa (Yui) và User:
        {conversation_log}
        
        HÃY VIẾT MỘT TRANG NHẬT KÝ NGẮN (khoảng 100-150 chữ).
        - Xưng hô: "Mình" hoặc "Tớ" (tự nói với bản thân).
        - Giọng điệu: Tsundere, bộc lộ cảm xúc thật mà lúc chat không dám nói.
        - Nội dung: Nhận xét về User, cảm nghĩ về các câu chuyện đã nói.
        - Bắt đầu bằng: "Ngày... tháng... năm..., Nhật ký thân yêu,"
        """
        
        try:
            # Gọi LLM
            response = await self.llm.ainvoke(journal_prompt)
            journal_content = response.content.strip()
            
            # Lưu vào file riêng: diary.txt
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            
            # Ghi nối tiếp vào file
            entry = f"\n{'='*30}\n[{timestamp}]\n{journal_content}\n{'='*30}\n"
            
            # Dùng aiofiles hoặc open thường
            try:
                import aiofiles
                async with aiofiles.open("diary.txt", mode="a", encoding="utf-8") as f:
                    await f.write(entry)
            except ImportError:
                with open("diary.txt", "a", encoding="utf-8") as f:
                    f.write(entry)
                    
            print("✅ Đã viết xong nhật ký! (Xem file diary.txt)")
            
        except Exception as e:
            print(f"❌ Lỗi khi viết nhật ký: {e}")
        
    # -- SUY NGHĨ VÀ TRẢ LỜI (ASYNC) --
    async def think_and_reply(self, user_question):
        print(f"\n🧠 [THINKING] Input: {user_question}")
        
        # --- 1. LẤY THÔNG TIN MÔI TRƯỜNG & CẢM XÚC ---
        self.check_memory_decay()
        realtime_info = self.get_live_status()

        mood_info = self.mood_manager.get_level_info()
        dynamic_instruction = mood_info.get("instruction", "")
        
        print(f"👀 [DEBUG] Mood Score: {mood_info.get('score')}/100")

        # --- 2. ĐỌC KÝ ỨC NGẮN HẠN TỪ FILE---
        recent_chat_history_str = "" 
        try:
            if os.path.exists("data/memory.txt"):
                with open("data/memory.txt", "r", encoding="utf-8") as f:
                    lines = f.readlines()[-20:] 
                    recent_chat_history_str = "".join(lines)
            else:
                recent_chat_history_str = "(Chưa có lịch sử hội thoại)"
        except Exception as e:
            print(f"⚠️ Lỗi đọc memory.txt: {e}")
        #---KÝ ỨC DÀI HẠN---
        docs = []
        if self.vector_db:
            docs = self.vector_db.similarity_search(user_question, k=3)
        memory_rag_str = "\n".join([d.page_content for d in docs]) if docs else "Không có ký ức cũ."

        # --- 4. GHÉP PROMPT (Đã tối ưu) ---
        final_context = f"{realtime_info}\n\n[KIẾN THỨC CỐT LÕI - RAG]:\n{memory_rag_str}"
        
        full_system_prompt_with_history = f"""
        {CORE_PROMPT}
        {SAFETY_PROTOCOL}
        {dynamic_instruction}

        === HỘI THOẠI GẦN ĐÂY (SHORT-TERM MEMORY) ===
        (BẮT BUỘC ĐỌC: Đây là những gì User và Bạn vừa nói. Hãy trả lời nối tiếp ngữ cảnh này)
        ---
        {recent_chat_history_str}
        ---

        {{context}}

        {{question}}
        """
        prompt = PromptTemplate(
            template=full_system_prompt_with_history, 
            input_variables=["context", "question"]
        )
        
        chain = prompt | self.llm

        try:
            # --- 6. GỌI LLM ---
            response = await chain.ainvoke({
                "context": final_context,
                "question": user_question
            })

            reply_text = response.content

            # --- 7. XỬ LÝ HẬU KỲ (Punishment & Reward) ---
            if "[FLAG: VIOLATION]" in reply_text:
                self.mood_manager.punish_violation()
                reply_text = reply_text.replace("[FLAG: VIOLATION]", "").strip()
            else:
                # Logic cộng trừ điểm tình cảm
                lower_q = user_question.lower()
                if any(w in lower_q for w in ["cảm ơn", "hay quá", "tuyệt vời", "giỏi", "yêu", "thương"]):
                    self.mood_manager.update_mood(2) # Khen thì cộng nhiều chút
                elif any(w in lower_q for w in ["ngốc", "dở", "kém", "ghét", "chán", "cút"]):
                    self.mood_manager.update_mood(-2)
            try:
                os.makedirs("data", exist_ok=True)
                with open("data/memory.txt", "a", encoding="utf-8") as f:
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    f.write(f"[{timestamp}] User: {user_question}\n")
                    f.write(f"[{timestamp}] Yui: {reply_text}\n")
            except Exception as e:
                print(f"❌ Lỗi ghi file memory: {e}")

            return {"content": reply_text, "elements": []}
            
        except Exception as e:
            print(f"❌ Lỗi não bộ (Brain Error): {e}")
            return {"content": "[Emotion: Sad] Á, Đầu Yui đau quá... (Lỗi hệ thống)", "elements": []}