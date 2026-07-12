markdown
# 🎵 Lyrics Aligner · пакетная синхронизация текстов
| | | | | | () |
| | __ _ _ __ | | __| | __| | __ _ _ __ ___ _ __ ___
| | / | '_ \/ __| |/ _ |/ / | / ` | ' \ / _ \ '/ |
| || (| | | | _ \ | (| | <| || (| | | | | / | _
_/_,|| ||/|_,||__|_,|| ||_|| |/

Batch lyrics alignment with Demucs + GPU

text
🚀 Быстрый старт в Google Colab
Просто откройте блокнот Colab и выполните эти команды:

bash
# 1. Монтируем Диск
from google.colab import drive
drive.mount('/content/drive')

# 2. Клонируем репозиторий
!git clone https://github.com/ваш-username/lyrics-aligner.git
%cd lyrics-aligner

# 3. Устанавливаем зависимости
!pip install -r requirements.txt

# 4. Настраиваем пути (укажите свою папку на Диске)
import os
MY_DRIVE = "/content/drive/MyDrive/LyricsAlign"
os.environ["LYRICS_BATCH_IN_DIR"] = f"{MY_DRIVE}/batch"
os.environ["LYRICS_BATCH_OUT_DIR"] = f"{MY_DRIVE}/batch_output"
os.environ["LYRICS_EXPERIMENT_DIR"] = f"{MY_DRIVE}/Эксперимет"
os.environ["LYRICS_DATA_DIR"] = "./data"
os.environ["LYRICS_CACHE_DIR"] = "./data/cache"
os.environ["LYRICS_JOBS_DIR"] = "./data/jobs"
os.environ["LYRICS_DEVICE"] = "auto"

# 5. Скачиваем модели Demucs
!python scripts/download_models.py htdemucs

# 6. Запускаем пакетную обработку
!python scripts/batch_align.py
📁 Структура папок на Google Диске
Перед запуском создайте на Диске папку (например, LyricsAlign) с такой структурой:

text
LyricsAlign/
├── batch/
│   ├── англ/          # треки на английском
│   │   ├── song.mp3
│   │   └── song.txt
│   ├── рус/           # на русском
│   └── англ + рус/    # смешанные
├── batch_output/      # сюда сохранятся результаты
└── Эксперимет/        # (опционально) для word-level экспериментов
🧠 Как это работает
Разделение аудио на вокал и инструментал (Demucs).

Распознавание фонем с помощью torchaudio (Wav2Vec2) — для точного выравнивания.

Динамическое программирование для привязки слов и строк к временным меткам.

Экспорт в lines.json (для строк) и words.json (для покадрового визуала).

🎛️ Параметры запуска
Вы можете указать язык и режим:

bash
# Для конкретного трека в эксперименте
python scripts/experiment_align.py --lang ru --force

# С пропуском разделения (если вокал уже выделен)
python scripts/batch_align.py --skip-separation
📊 Результаты
После обработки в batch_output/lines/ появляются файлы <имя>.lines.json:

json
{
  "lines": [
    {"text": "Первая строка", "start": 1.23, "end": 3.45},
    ...
  ],
  "quality": {"line_coverage": 0.95}
}
Также генерируется общий отчёт batch_report.json.

❓ Частые проблемы
Модели Demucs не скачиваются – запустите scripts/download_models.py отдельно.

Не хватает памяти – уменьшите количество треков в папке или используйте --mode=fast.

Нет GPU – в Colab выберите Среда выполнения → Сменить тип → GPU.

📄 Лицензия
MIT — делайте с кодом что угодно, но упоминайте автора.

🌟 Благодарности
Demucs за разделение аудио.

TorchAudio за Wav2Vec2.

Сделано с ❤️ для синхронизации текстов песен.
