# JSON Flatten CLI & Library

Утилита командной строки и библиотека Python для уплощения (flatten) и восстановления (unflatten) вложенных структур JSON и потоков NDJSON / JSON Lines.

## Возможности

- **Рекурсивное уплощение**: преобразует глубоко вложенные словари и списки в плоский формат с составными ключами (`a.b.0.c`).
- **Восстановление структуры (Unflatten)**: корректно реконструирует вложенные словари и списки из плоских ключей.
- **Поддержка NDJSON / JSON Lines**: построчная потоковая обработка больших объемов данных без загрузки всего файла в память.
- **Ограничение глубины (`--max-depth`)**: возможность остановить разворачивание на заданном уровне.
- **Устойчивость к ошибкам (`--ignore-errors`)**: пропуск некорректных строк в режиме NDJSON с предупреждением в `stderr`.
- **Настраиваемый разделитель (`-s`, `--sep`)**: использование любого символа разделителя (например, `/`, `_`, `:`).
- **Экспорт в табличные форматы (`--format csv/tsv`)**: преобразование массивов объектов JSON и потоков NDJSON в CSV или TSV с сохранением порядка колонок и корректным экранированием спецсимволов.

---

## Использование в командной строке (CLI)

```bash
python json_flatten.py [file] [опции]
```

Если аргумент `file` не указан или равен `-`, данные читаются из стандартного ввода `stdin`.

### Доступные флаги

- `file`: путь к файлу JSON / NDJSON или `-` для чтения из stdin.
- `-u`, `--unflatten`: режим восстановления вложенной структуры из плоского JSON.
- `-s SEP`, `--sep SEP`: разделитель ключей (по умолчанию: `.`).
- `-n`, `--ndjson`: построчный режим обработки NDJSON / JSON Lines (вывод в компактном виде).
- `--max-depth N`: максимальная глубина уплощения (целое число).
- `--ignore-errors`: пропуск некорректных строк JSON в режиме NDJSON с выводом предупреждения в `stderr`.
- `--format {json,csv,tsv}`: формат вывода данных (по умолчанию: `json`).

---

## Примеры использования

### 1. Чтение из stdin
```bash
echo '{"user": {"name": "Alice", "role": "admin"}}' | python json_flatten.py
```
Вывод:
```json
{
  "user.name": "Alice",
  "user.role": "admin"
}
```

### 2. Чтение из файла
```bash
python json_flatten.py data.json
```

### 3. Пользовательский разделитель (`-s`)
```bash
echo '{"a": {"b": 10}}' | python json_flatten.py -s "/"
```
Вывод:
```json
{
  "a/b": 10
}
```

### 4. Восстановление структуры (`-u` / `--unflatten`)
```bash
echo '{"user.name": "Alice", "user.age": 30}' | python json_flatten.py -u
```
Вывод:
```json
{
  "user": {
    "name": "Alice",
    "age": 30
  }
}
```

### 5. Ограничение глубины (`--max-depth`)
```bash
echo '{"a": {"b": {"c": 1}}}' | python json_flatten.py --max-depth 1
```
Вывод:
```json
{
  "a": {
    "b": {
      "c": 1
    }
  }
}
```

```bash
echo '{"a": {"b": {"c": 1}}}' | python json_flatten.py --max-depth 2
```
Вывод:
```json
{
  "a.b": {
    "c": 1
  }
}
```

### 6. Построчный режим NDJSON (`-n`)
```bash
echo -e '{"user": {"id": 1}}\n{"user": {"id": 2}}' | python json_flatten.py -n
```
Вывод:
```ndjson
{"user.id":1}
{"user.id":2}
```

### 7. Игнорирование ошибок в NDJSON (`--ignore-errors`)
```bash
echo -e '{"a": 1}\nNOT_A_JSON\n{"b": 2}' | python json_flatten.py -n --ignore-errors
```
Вывод в stdout:
```ndjson
{"a":1}
{"b":2}
```
В stderr выводится предупреждение:
```
Warning: skipping invalid JSON line: ...
```

### 8. Экспорт массива объектов в CSV (`--format csv`)
```bash
echo '[{"id": 1, "user": {"name": "Alice"}}, {"id": 2, "user": {"name": "Bob, Jr."}}]' | python json_flatten.py --format csv
```
Вывод:
```csv
id,user.name
1,Alice
2,"Bob, Jr."
```

### 9. Экспорт потока NDJSON в TSV (`--format tsv`)
```bash
echo -e '{"host": "srv1", "metrics": {"cpu": 12.5}}\n{"host": "srv2", "metrics": {"cpu": 45.0}}' | python json_flatten.py -n --format tsv
```
Вывод:
```tsv
host	metrics.cpu
srv1	12.5
srv2	45.0
```

---

## Использование в коде Python

```python
from json_flatten import flatten, unflatten, process_ndjson_line, to_tabular

# Уплощение
nested = {"profile": {"name": "Bob", "tags": ["dev", "lead"]}}
flat = flatten(nested, sep=".")
# {'profile.name': 'Bob', 'profile.tags.0': 'dev', 'profile.tags.1': 'lead'}

# Восстановление
restored = unflatten(flat, sep=".")
# {"profile": {"name": "Bob", "tags": ["dev", "lead"]}}

# Ограничение глубины
shallow = flatten(nested, max_depth=1)
# {'profile': {'name': 'Bob', 'tags': ['dev', 'lead']}}

# Экспорт в CSV / TSV
records = [flat, {"profile.name": "Alice", "profile.tags.0": "admin"}]
csv_data = to_tabular(records, delimiter=",")
tsv_data = to_tabular(records, delimiter="\t")
```
