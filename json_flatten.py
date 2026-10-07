import argparse
import csv
import io
import json
import sys
from typing import Any, Dict, Iterable, Iterator, List, Optional, TextIO, Union


def flatten(
    data: Any,
    sep: str = ".",
    parent_key: str = "",
    max_depth: Optional[int] = None,
    current_depth: int = 0,
) -> Dict[str, Any]:
    """Рекурсивно разворачивает вложенный JSON/словарь в плоский словарь с поддержкой ограничения глубины."""
    items: Dict[str, Any] = {}

    if max_depth is not None and current_depth >= max_depth and parent_key:
        items[parent_key] = data
        return items

    if isinstance(data, dict):
        if not data and parent_key:
            items[parent_key] = {}
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
            items.update(
                flatten(
                    v,
                    sep=sep,
                    parent_key=new_key,
                    max_depth=max_depth,
                    current_depth=current_depth + 1,
                )
            )
    elif isinstance(data, list):
        if not data and parent_key:
            items[parent_key] = []
        for i, v in enumerate(data):
            new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
            items.update(
                flatten(
                    v,
                    sep=sep,
                    parent_key=new_key,
                    max_depth=max_depth,
                    current_depth=current_depth + 1,
                )
            )
    else:
        items[parent_key] = data

    return items


def unflatten(
    data: Dict[str, Any],
    sep: str = ".",
) -> Union[Dict[str, Any], List[Any], Any]:
    """Восстанавливает исходную структуру из плоского словаря."""
    if not isinstance(data, dict) or not data:
        return {}

    result: Dict[str, Any] = {}

    for composite_key, value in data.items():
        keys = composite_key.split(sep)
        curr = result
        for i, k in enumerate(keys[:-1]):
            if k not in curr or not isinstance(curr[k], dict):
                curr[k] = {}
            curr = curr[k]
        curr[keys[-1]] = value

    return _reconstruct_lists(result)


def _reconstruct_lists(obj: Any) -> Any:
    """Вспомогательная функция для преобразования целочисленных ключей обратно в списки."""
    if isinstance(obj, dict):
        if obj and all(k.isdigit() for k in obj.keys()):
            int_keys = [int(k) for k in obj.keys()]
            if sorted(int_keys) == list(range(len(int_keys))):
                return [_reconstruct_lists(obj[str(i)]) for i in range(len(int_keys))]
        return {k: _reconstruct_lists(v) for k, v in obj.items()}
    return obj


def process_ndjson_line(
    line: str,
    unflatten_mode: bool = False,
    sep: str = ".",
    max_depth: Optional[int] = None,
    ignore_errors: bool = False,
) -> str:
    """Обрабатывает одну строку NDJSON: парсит, уплощает/восстанавливает и сериализует в компактный JSON."""
    stripped = line.strip()
    if not stripped:
        return ""
    try:
        data = json.loads(stripped)
    except Exception as e:
        if ignore_errors:
            sys.stderr.write(f"Warning: skipping invalid JSON line: {e}\n")
            return ""
        raise

    if unflatten_mode:
        res = unflatten(data, sep=sep)
    else:
        res = flatten(data, sep=sep, max_depth=max_depth)
    return json.dumps(res, separators=(",", ":"), ensure_ascii=False)


def process_ndjson_stream(
    stream: Iterable[str],
    unflatten_mode: bool = False,
    sep: str = ".",
    max_depth: Optional[int] = None,
    ignore_errors: bool = False,
) -> Iterator[str]:
    """Итератор по строкам NDJSON-потока, возвращающий обработанные строки."""
    for line in stream:
        processed = process_ndjson_line(
            line,
            unflatten_mode=unflatten_mode,
            sep=sep,
            max_depth=max_depth,
            ignore_errors=ignore_errors,
        )
        if processed:
            yield processed


def to_tabular(
    records: List[Dict[str, Any]],
    delimiter: str = ",",
) -> str:
    """Конвертирует список плоских словарей в строку CSV или TSV."""
    output = io.StringIO()
    write_tabular(records, output, delimiter=delimiter)
    return output.getvalue()


def write_tabular(
    records: List[Dict[str, Any]],
    output: TextIO,
    delimiter: str = ",",
) -> None:
    """Записывает список плоских словарей в поток вывода в формате CSV или TSV."""
    if not records:
        return

    all_keys: List[str] = []
    seen = set()
    for row in records:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                all_keys.append(k)

    writer = csv.writer(output, delimiter=delimiter, lineterminator="\n")
    writer.writerow(all_keys)

    for row in records:
        formatted_row = []
        for k in all_keys:
            val = row.get(k)
            if val is None:
                formatted_row.append("")
            elif isinstance(val, (dict, list)):
                formatted_row.append(json.dumps(val, ensure_ascii=False))
            else:
                formatted_row.append(str(val))
        writer.writerow(formatted_row)


def get_type_name(val: Any) -> str:
    """Возвращает нормализованное имя типа данных для JSON."""
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "bool"
    if isinstance(val, int):
        return "int"
    if isinstance(val, float):
        return "float"
    if isinstance(val, str):
        return "str"
    if isinstance(val, list):
        return "list"
    if isinstance(val, dict):
        return "dict"
    return type(val).__name__


def _extract_array_lengths(
    data: Any,
    sep: str = ".",
    parent_path: str = "",
    array_lengths: Optional[Dict[str, List[int]]] = None,
) -> Dict[str, List[int]]:
    if array_lengths is None:
        array_lengths = {}

    if isinstance(data, list):
        path_key = parent_path if parent_path else "[]"
        if path_key not in array_lengths:
            array_lengths[path_key] = []
        array_lengths[path_key].append(len(data))
        for i, item in enumerate(data):
            child_path = f"{parent_path}{sep}{i}" if parent_path else str(i)
            _extract_array_lengths(item, sep=sep, parent_path=child_path, array_lengths=array_lengths)
    elif isinstance(data, dict):
        for k, v in data.items():
            child_path = f"{parent_path}{sep}{k}" if parent_path else str(k)
            _extract_array_lengths(v, sep=sep, parent_path=child_path, array_lengths=array_lengths)

    return array_lengths


def collect_stats(
    data_items: Union[Any, Iterable[Any]],
    sep: str = ".",
) -> Dict[str, Any]:
    """Собирает аналитическую статистику структуры данных (total_keys, max_depth, key_types, array_lengths)."""
    if isinstance(data_items, (dict, str, int, float, bool)) or data_items is None:
        items_list = [data_items]
    elif isinstance(data_items, list):
        items_list = data_items
    else:
        items_list = list(data_items)

    all_keys = set()
    max_depth = 0
    key_types: Dict[str, set] = {}
    array_lengths_raw: Dict[str, List[int]] = {}

    for item in items_list:
        _extract_array_lengths(item, sep=sep, array_lengths=array_lengths_raw)

        flat = flatten(item, sep=sep)
        for k, v in flat.items():
            if not k:
                continue
            all_keys.add(k)
            depth = len(k.split(sep))
            if depth > max_depth:
                max_depth = depth
            if k not in key_types:
                key_types[k] = set()
            key_types[k].add(get_type_name(v))

    return {
        "total_keys": len(all_keys),
        "max_depth": max_depth,
        "key_types": {k: sorted(list(types)) for k, types in sorted(key_types.items())},
        "array_lengths": {
            k: sorted(list(set(lens))) for k, lens in sorted(array_lengths_raw.items())
        },
    }


def main(argv: Union[List[str], None] = None) -> None:
    parser = argparse.ArgumentParser(description="Уплощение и восстановление вложенных JSON-структур.")
    parser.add_argument(
        "file",
        nargs="?",
        default="-",
        help="Путь к файлу JSON или '-' для чтения из stdin (по умолчанию: '-')",
    )
    parser.add_argument(
        "-u",
        "--unflatten",
        action="store_true",
        help="Восстановить вложенную структуру из плоского JSON",
    )
    parser.add_argument(
        "-s",
        "--sep",
        default=".",
        help="Разделитель ключей (по умолчанию: '.')",
    )
    parser.add_argument(
        "-n",
        "--ndjson",
        action="store_true",
        help="Построчная обработка потока NDJSON / JSON Lines",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Максимальная глубина уплощения (целое число)",
    )
    parser.add_argument(
        "--ignore-errors",
        action="store_true",
        help="Пропускать некорректные JSON-строки в режиме NDJSON с выводом предупреждения в stderr",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "tsv"],
        default="json",
        help="Формат вывода данных: json, csv или tsv (по умолчанию: json)",
    )
    parser.add_argument(
        "--stats",
        "--schema",
        action="store_true",
        dest="stats",
        help="Вывести JSON со статистикой структуры данных (total_keys, max_depth, key_types, array_lengths)",
    )

    args = parser.parse_args(argv)

    delimiter = "," if args.format == "csv" else "\t"

    if args.ndjson:
        if args.file == "-" or not args.file:
            stream = sys.stdin
            should_close = False
        else:
            stream = open(args.file, "r", encoding="utf-8")
            should_close = True

        try:
            if args.stats:
                items_list: List[Any] = []
                for line in stream:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        obj = json.loads(stripped)
                    except Exception as e:
                        if args.ignore_errors:
                            sys.stderr.write(f"Warning: skipping invalid JSON line: {e}\n")
                            continue
                        raise
                    items_list.append(obj)
                stats = collect_stats(items_list, sep=args.sep)
                print(json.dumps(stats, indent=2, ensure_ascii=False))
            elif args.format in ("csv", "tsv"):
                records: List[Dict[str, Any]] = []
                for line in stream:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        obj = json.loads(stripped)
                    except Exception as e:
                        if args.ignore_errors:
                            sys.stderr.write(f"Warning: skipping invalid JSON line: {e}\n")
                            continue
                        raise
                    flat = flatten(obj, sep=args.sep, max_depth=args.max_depth)
                    records.append(flat)
                write_tabular(records, sys.stdout, delimiter=delimiter)
            else:
                for out_line in process_ndjson_stream(
                    stream,
                    unflatten_mode=args.unflatten,
                    sep=args.sep,
                    max_depth=args.max_depth,
                    ignore_errors=args.ignore_errors,
                ):
                    print(out_line)
        finally:
            if should_close:
                stream.close()
        return

    if args.file == "-" or not args.file:
        raw_data = sys.stdin.read()
    else:
        with open(args.file, "r", encoding="utf-8") as f:
            raw_data = f.read()

    data = json.loads(raw_data)

    if args.stats:
        stats = collect_stats(data, sep=args.sep)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return

    if args.format in ("csv", "tsv"):
        if isinstance(data, list):
            records = [
                flatten(item, sep=args.sep, max_depth=args.max_depth)
                if isinstance(item, (dict, list))
                else {"": item}
                for item in data
            ]
        elif isinstance(data, dict):
            records = [flatten(data, sep=args.sep, max_depth=args.max_depth)]
        else:
            records = [{"": data}]
        write_tabular(records, sys.stdout, delimiter=delimiter)
        return

    if args.unflatten:
        result = unflatten(data, sep=args.sep)
    else:
        result = flatten(data, sep=args.sep, max_depth=args.max_depth)

    print(json.dumps(result, indent=2, ensure_ascii=False))



if __name__ == "__main__":
    main()

