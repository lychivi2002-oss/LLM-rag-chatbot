import chainlit as cl
import re
import asyncio
import time
import os 

# Import class não bộ và config cảm xúc của bạn
from brain.modules_brain import YuiBrain 
from brain.emotion import EMOTION_SET

print("🚀 Đang khởi động Yui App...")

@cl.on_chat_start
async def start():
    brain = YuiBrain()
    
    brain.learn_knowledge("knowledge.txt") 
    cl.user_session.set("brain", brain)

    
    wakeup_data = EMOTION_SET.get("Wakeup", EMOTION_SET.get("Neutral"))
    image_path = wakeup_data["image_file"]

    intro_image = cl.Image(
        path=image_path,
        name="yui_avatar",
        display="inline"
    )

    await cl.Message(
        content="[Emotion: Wakeup] Oa...(Ngáp)... Chào buổi sáng! Cậu cần tớ giúp gì không?",
        elements=[intro_image]
    ).send()

@cl.on_message
async def main(message: cl.Message):
    # --- 0. LẤY BRAIN TỪ SESSION ---
    brain = cl.user_session.get("brain")
    if not brain:
        await cl.Message(content="❌ Lỗi: Brain chưa khởi động. Hãy reset trang!").send()
        return

    # --- 1. CHECK SPAM (Ngăn user nhấn liên tục khi đang xử lý) ---
    if cl.user_session.get("typing"):
        return 
    cl.user_session.set("typing", True)

    msg = None 

    try:
        # --- 2. XỬ LÝ TIME AWARENESS ---
        last_time = cl.user_session.get("last_interaction")
        current_time = time.time()
        
        if last_time is None: last_time = current_time
        
        duration = current_time - last_time
        minutes_gone = duration / 60
        cl.user_session.set("last_interaction", current_time)

        system_note = ""
        if 0 < duration < 2.0: 
            system_note = "(HỆ THỐNG: User nhắn rất nhanh, có vẻ đang hào hứng. Hãy đáp lại nhiệt tình)."
        elif minutes_gone > 720: 
            system_note = "(HỆ THỐNG: User bỏ đi hơn 12 tiếng. Hãy tỏ ra hơi dỗi vì bị bỏ rơi)."
        elif minutes_gone > 60:
            system_note = "(HỆ THỐNG: User im lặng hơn 1 tiếng. Hãy hỏi thăm nhẹ nhàng)."

        final_input = f"{message.content} \n\n{system_note}"

        # --- 3. KHỞI TẠO TIN NHẮN PHẢN HỒI ---
        msg = cl.Message(content="")
        await msg.send()

        try:
            full_response = await brain.think_and_reply(final_input) 
            if isinstance(full_response, dict):
                full_response = full_response.get("content", "")
                
        except Exception as e:
            print(f"Lỗi Brain: {e}")
            full_response = "[Emotion: Sad] Xin lỗi... đầu tớ hơi rối một chút. (Lỗi xử lý)"

        # --- 4. XỬ LÝ TEXT & ẢNH BIỂU CẢM ---
        emotion_tag = "Neutral"
        clean_text = full_response
        
        match = re.search(r"\[Emotion:\s*([^\]]+)\]", full_response)
        if match:
            emotion_tag = match.group(1).strip()
            clean_text = full_response.replace(match.group(0), "").strip()

        if emotion_tag not in EMOTION_SET:
            emotion_tag = "Neutral"

        img_path = EMOTION_SET[emotion_tag]["image_file"]
        
        if os.path.exists(img_path):
            img = cl.Image(path=img_path, name="yui_avatar", display="inline")
            msg.elements = [img]
            await msg.update() 
        
        # --- 5. HIỆU ỨNG GÕ CHỮ (TYPING EFFECT) ---
        displayed_text = ""
        for char in clean_text:
            displayed_text += char
            await msg.stream_token(char)
            
            # Tốc độ gõ linh hoạt
            pause = 0.01
            if char in ".?!": pause = 0.2
            elif char in ",\n": pause = 0.08
            await asyncio.sleep(pause)

    except Exception as e:
        print(f"Lỗi hệ thống: {e}")
        if msg:
            msg.content += f"\n\n(Lỗi kỹ thuật: {e})"
            await msg.update()
        else:
            await cl.Message(content=f"[Lỗi nghiêm trọng] {e}").send()

    finally:
        # --- 6. CLEANUP ---
        cl.user_session.set("typing", False)
        if msg:
            await msg.update()

@cl.on_chat_end
async def end():
    brain = cl.user_session.get("brain")
    if brain:
        print("🛑 User đã thoát. Đang lưu ký ức cuối ngày...")
        
        if asyncio.iscoroutinefunction(brain.save_memory):
            await brain.save_memory()
        else:
            brain.save_memory()