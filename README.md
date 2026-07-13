<div align="center">

# 🎵 Lyrics Aligner
### Пакетная синхронизация текстов песен

```bash

  __  ____  ____  __   _            _       
 |  \/  \ \/ /  \/  | | |  _  _ _ _(_)__ ___
 | |\/| |>  <| |\/| | | |_| || | '_| / _(_-<
 |_|  |_/_/\_\_|  |_| |____\_, |_| |_\__/__/
                           |__/


                                                              
```

**Batch lyrics alignment with Demucs + GPU**

</div>

---

## 🚀 Быстрый старт в Google Colab

Откройте новый Colab-блокнот и выполните команды ниже:

```python
# 1. Монтируем Google Drive
from google.colab import drive
drive.mount('/content/drive')
```

```bash
# 2. Клонируем репозиторий
!git clone https://github.com/ваш-username/lyrics-aligner.git
%cd lyrics-aligner
```

```bash
# 3. Устанавливаем зависимости
!pip install -r requirements.txt
```

```python
# 4. Настраиваем пути
import os

MY_DRIVE = "/content/drive/MyDrive/LyricsAlign"

os.environ["LYRICS_BATCH_IN_DIR"] = f"{MY_DRIVE}/batch"
os.environ["LYRICS_BATCH_OUT_DIR"] = f"{MY_DRIVE}/batch_output"
os.environ["LYRICS_EXPERIMENT_DIR"] = f"{MY_DRIVE}/Эксперимет"
os.environ["LYRICS_DATA_DIR"] = "./data"
os.environ["LYRICS_CACHE_DIR"] = "./data/cache"
os.environ["LYRICS_JOBS_DIR"] = "./data/jobs"
os.environ["LYRICS_DEVICE"] = "auto"
```

```bash
# 5. Скачиваем модели Demucs
!python scripts/download_models.py htdemucs
```

```bash
# 6. Запускаем пакетную обработку
!python scripts/batch_align.py
```

---

## 📁 Структура папок на Google Диске

Создайте на Диске папку `LyricsAlign` со следующей структурой:

```text
LyricsAlign/
├── batch/
│   ├── англ/
│   │   ├── song.mp3
│   │   └── song.txt
│   ├── рус/
│   └── англ + рус/
├── batch_output/
└── Эксперимет/
```

- `batch/` — входные треки и тексты.
- `batch_output/` — результаты обработки.
- `Эксперимет/` — опциональная папка для word-level экспериментов.

---

## 🧠 Как это работает

- Сначала аудио разделяется на вокал и инструментал с помощью Demucs.
- Затем распознаются фонемы через `torchaudio` / Wav2Vec2 для точного выравнивания.
- После этого используется динамическое программирование для привязки строк и слов ко времени.
- На выходе генерируются `lines.json` и `words.json` для дальнейшего использования.

---

## 🎛️ Параметры запуска

```bash
# Для конкретного трека в эксперименте
python scripts/experiment_align.py --lang ru --force
```

```bash
# Если вокал уже выделен, пропускаем разделение
python scripts/batch_align.py --skip-separation
```

```bash
# Быстрый режим
python scripts/batch_align.py --mode fast
```

---

## 📊 Результаты

После обработки в `batch_output/lines/` появятся файлы вида:

```json
{
  "lines": [
    {"text": "Первая строка", "start": 1.23, "end": 3.45}
  ],
  "quality": {
    "line_coverage": 0.95
  }
}
```

Также создаётся общий отчёт `batch_report.json`.

---

## ❓ Частые проблемы

- **Модели Demucs не скачиваются** — запустите `scripts/download_models.py` отдельно.
- **Не хватает памяти** — уменьшите количество треков или используйте `--mode fast`.
- **Нет GPU** — в Colab выберите `Среда выполнения → Сменить тип среды выполнения → GPU`.

---

## 📄 Лицензия

MIT — используйте код свободно, но сохраняйте авторство.

---

## 🌟 Благодарности

- [Demucs](https://github.com/facebookresearch/demucs) — за разделение аудио.
- [TorchAudio](https://pytorch.org/audio/) — за Wav2Vec2.
- Сделано с ❤️ для синхронизации текстов песен.
