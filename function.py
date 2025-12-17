import datetime
import os
import aiofiles 
import json
from .emotion import MOOD_LEVELS, get_dynamic_prompt
class MemoryHandler:
    def __init__(self, llm_model, file_path="memory.txt", max_turns=10):
        self.llm = llm_model
        self.file_path = file_path
        self.daily_buffer = []
        self.max_turn = max_turns
        
        # Tạo file nếu chưa có
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write("--- LONG TERM MEMORY OF YUI ---\n")

    def _get_summary_prompt(self, text_to_summarize):
        """Tạo prompt tóm tắt (Hàm nội bộ)"""
        return f"""
Dưới đây là đoạn hội thoại. Hãy trích xuất CHỈ những thông tin quan trọng về người dùng (sở thích, tên, sự kiện đời tư, thói quen).
- Viết ngắn gọn 1 dòng.
- Nếu chỉ là chào hỏi xã giao, trả lời: NONE

Hội thoại:
{text_to_summarize}
"""

    def add_to_buffer(self, user_msg, bot_msg):
        """Thêm hội thoại vào bộ đệm, chưa lưu ngay"""
        self.daily_buffer.append(f"User: {user_msg}")
        self.daily_buffer.append(f"Yui: {bot_msg}")

        if len(self.daily_buffer) >= self.max_turn * 2:
            
            pass 
            
    async def save_fragment_memory(self):
        """Xử lý tóm tắt và ghi vào file (Async)"""
        if not self.daily_buffer:
            return

        full_conversation = "\n".join(self.daily_buffer)
        prompt_text = self._get_summary_prompt(full_conversation)
        
        try:
            
            response = await self.llm.ainvoke(prompt_text)
            summary = response.content.strip() 

            if "NONE" not in summary and len(summary) > 5:
                print(f" [Memory] Đang ghi nhớ: {summary}")
                await self.append_to_file(summary)
            else:
                print("🗑️ [Memory] Không có gì đáng nhớ, bỏ qua.")
            
            # Xóa buffer sau khi xử lý xong
            self.daily_buffer = [] 

        except Exception as e:
            print(f"⚠️ Lỗi tóm tắt ký ức: {e}")

    async def append_to_file(self, text):
        """Ghi xuống file ổ cứng"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        line = f"[{timestamp}] {text}\n"
        
        try:
            async with aiofiles.open(self.file_path, mode="a", encoding="utf-8") as f:
                await f.write(line)
        except NameError:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(line)
                
    async def write_daily_journal(self):
        """
        Viết nhật ký cảm xúc cuối ngày (Lưu vào diary.txt).
        """
        if not self.daily_buffer:
            return

        print("✍️ Yui đang viết nhật ký...")
        conversation_log = "\n".join(self.daily_buffer)
        
        journal_prompt = f"""
        Dựa trên đoạn hội thoại hôm nay:
        {conversation_log}
        
        HÃY VIẾT MỘT TRANG NHẬT KÝ NGẮN (khoảng 100 chữ).
        - Vai: Yui (Tsundere).
        - Nội dung: Cảm nghĩ về User hôm nay.
        - Bắt đầu bằng: "Nhật ký thân mến,"
        """
        
        try:
            response = await self.llm.ainvoke(journal_prompt)
            journal_content = response.content.strip()
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            entry = f"\n{'='*20}\n[{timestamp}]\n{journal_content}\n{'='*20}\n"
            
            # Ghi vào file diary.txt
            async with aiofiles.open("diary.txt", mode="a", encoding="utf-8") as f:
                await f.write(entry)
                
            print("✅ Đã viết xong nhật ký (diary.txt)!")
            
            self.daily_buffer = []
            
        except Exception as e:
            print(f"❌ Lỗi viết nhật ký: {e}")

    def load_memory(self, limit=2000):
        """
        Đọc ký ức để nhét vào Brain.
        limit: Giới hạn số ký tự đọc lên (để tránh tràn context model)
        """
        if not os.path.exists(self.file_path):
            return ""
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = f.read()
                return data[-limit:] 
        except Exception as e:
            print(f"Lỗi đọc file memory: {e}")
            return ""

#2. --MOOD SYSTEM--
class MoodManager:
    def __init__(self, file_path="data/mood.json"):
        self.file_path = file_path
        # Đảm bảo thư mục data tồn tại
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        self.mood_score = self.load_mood()

    def load_mood(self):
        """Đọc điểm từ file json"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("score", 30) # Mặc định 30 điểm (Người lạ)
            except Exception as e:
                print(f"⚠️ Lỗi đọc mood: {e}")
                return 30
        return 30

    def save_mood(self):
        """Lưu điểm xuống file json"""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({"score": self.mood_score}, f)
        except Exception as e:
            print(f"⚠️ Lỗi lưu mood: {e}")

    def update_mood(self, delta):
        """Cập nhật điểm cảm xúc (+ hoặc -)"""
        self.mood_score += delta
        
        self.mood_score = max(0, min(100, self.mood_score))
        
        self.save_mood()
        print(f"❤️ Mood updated: {delta} -> Current: {self.mood_score}/100")
        return self.mood_score

    def punish_violation(self):
        """Trừ điểm nặng khi vi phạm"""
        PENALTY = -15
        old_score = self.mood_score
        self.update_mood(PENALTY)
        print(f"⚠️ [VIOLATION] Phạt! {old_score} -> {self.mood_score}")

    def get_level_info(self):
        
        current_level_name = "Stranger"
        for name, data in MOOD_LEVELS.items():
            if data["min"] <= self.mood_score <= data["max"]:
                current_level_name = name
                break
        instruction_text = get_dynamic_prompt(self.mood_score)

        return {
            "score": self.mood_score,
            "level": current_level_name,
            "instruction": instruction_text 
        }




        
    



