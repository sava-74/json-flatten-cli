import argparse
import json
import sys
from typing import Any, Dict, Iterable, Iterator, List, Optional, Union


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
    if not data:
        return {}

    result: Dict[str, Any] = {}

    for composite_key, value in data.items():
        keys = composite_key.split(sep)
        curr = result
        for i, k in enumerate(keys[:-1]):
            if k not in curr:
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

    args = parser.parse_args(argv)

    if args.ndjson:
        if args.file == "-" or not args.file:
            for out_line in process_ndjson_stream(
                sys.stdin,
                unflatten_mode=args.unflatten,
                sep=args.sep,
                max_depth=args.max_depth,
                ignore_errors=args.ignore_errors,
            ):
                print(out_line)
        else:
            with open(args.file, "r", encoding="utf-8") as f:
                for out_line in process_ndjson_stream(
                    f,
                    unflatten_mode=args.unflatten,
                    sep=args.sep,
                    max_depth=args.max_depth,
                    ignore_errors=args.ignore_errors,
                ):
                    print(out_line)
        return

    if args.file == "-" or not args.file:
        raw_data = sys.stdin.read()
    else:
        with open(args.file, "r", encoding="utf-8") as f:
            raw_data = f.read()

    data = json.loads(raw_data)

    if args.unflatten:
        result = unflatten(data, sep=args.sep)
    else:
        result = flatten(data, sep=args.sep, max_depth=args.max_depth)

    print(json.dumps(result, indent=2, ensure_ascii=False))



if __name__ == "__main__":
    main()

