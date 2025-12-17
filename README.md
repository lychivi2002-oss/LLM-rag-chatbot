# 🌸 Yui - AI Girlfriend (Tsundere Edition)

> An intelligent, emotionally aware AI companion featuring a hybrid memory system, real-time context awareness, and a dynamic "Tsundere" personality engine.

## 📖 Overview

**Yui** is more than just a chatbot wrapper. She is a sophisticated **AI Companion** designed to simulate a living relationship. Built with **Google Gemini 2.0 Flash**, **LangChain**, and **Chainlit**, Yui possesses a unique "Tsundere" personality that evolves over time.

Unlike standard stateless bots, Yui features:
- **Persistent Memory:** She remembers your name, nicknames ("Camille"), and shared history even after the server restarts.
- **Emotional Intelligence:** Her attitude shifts from "Cold/Hostile" to "Sweet/Loving" based on an internal affinity score.
- **Context Awareness:** She knows the real-time weather, time of day, and can detect if you are typing fast (excited) or leaving her on read (ignored).

---

## ✨ Key Features

### 🧠 1. Hybrid Memory Architecture (RAG + Buffer)
Yui utilizes a two-tier memory system to ensure continuity:
* **Short-Term Context (File-based):** A sliding window buffer stored in `data/memory.txt` allows Yui to retain immediate conversation context and recall details from previous sessions instantly.
* **Long-Term Knowledge (RAG - ChromaDB):** Uses a Vector Database to retrieve relevant background information from `knowledge.txt` only when necessary, optimizing token usage.

### ❤️ 2. Dynamic Mood Engine
The core of Yui's personality is a custom-built **Mood Manager**:
* **Affinity Score (0-100):** Your interactions affect her mood. Compliments increase the score; rude behavior decreases it.
* **Dynamic Prompting:** The system prompt injected into the LLM changes dynamically based on her relationship level:
    * *Stranger (0-25):* Cold, short answers.
    * *Acquaintance (26-50):* Polite but distant.
    * *Friend (51-75):* Tsundere (Hot/Cold), playful teasing.
    * *Lover (76-100):* Dere-dere (Sweet), affectionate.
* **Visual Feedback:** Yui automatically selects expressions (images) matching the sentiment of her response (e.g., Blushing when shy, Pouting when angry).

### ⚡ 3. Real-Time Context Awareness
* **Time & Weather:** Integrated with weather APIs to comment on the current weather in Vietnam or greet you appropriately based on the time of day.
* **Interaction Speed:** The system detects your typing cadence.
    * *Typing fast:* She perceives you as excited.
    * *Long silence:* She might express loneliness or annoyance.

---

## 🛠️ Tech Stack

* **Language:** Python 3.10+
* **LLM Core:** Google Gemini 2.0 Flash
* **Orchestration:** LangChain (LCEL)
* **UI Framework:** Chainlit
* **Vector Database:** ChromaDB
* **Utilities:** `python-dotenv`, `aiofiles`, `pandas`

---
### 🎥 Demo Video

[![Watch the video][(https://img.youtube.com/vi/ID_VIDEO_CUA_BAN/0.jpg)](https://www.youtube.com/watch?v=ID_VIDEO_CUA_BAN)](https://youtu.be/NQfYL0o1yWM)

*(Bấm vào ảnh trên để xem video demo)*
