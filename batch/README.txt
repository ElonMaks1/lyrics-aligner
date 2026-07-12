Положите в каждую папку пары файлов с ОДИНАКОВЫМ именем:

  batch\англ\       — весь текст на английском  → язык EN
  batch\рус\        — весь текст на русском     → язык RU
  batch\англ + рус\ — смешанный текст           → язык RU+EN

  Song.mp3  +  Song.txt

Запуск: batch_run.bat

Результат (только .lines.json, все треки в одной папке):
  batch_output\lines\Song.lines.json
  batch_output\lines\Другой трек.lines.json
  ...

Проверка синхронизации в браузере:
  http://127.0.0.1:8765/verify
