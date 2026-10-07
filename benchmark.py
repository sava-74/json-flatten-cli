import json
import time
from typing import Any, Dict, List
from json_flatten import flatten, unflatten, process_ndjson_stream


def generate_large_nested_dict(target_keys: int = 50_000) -> Dict[str, Any]:
    """Генерирует глубоко вложенную структуру данных с заданным количеством ключей."""
    data: Dict[str, Any] = {}
    # Создаем иерархическую структуру: 500 групп по 10 объектов с 10 полями = 50,000 ключей
    groups = 500
    items_per_group = 10

    key_count = 0
    for g in range(groups):
        group_key = f"group_{g}"
        data[group_key] = {}
        for item in range(items_per_group):
            item_key = f"item_{item}"
            data[group_key][item_key] = {
                "id": key_count,
                "name": f"Entity_{key_count}",
                "config": {
                    "enabled": True,
                    "retries": 3,
                    "metrics": {
                        "cpu": 12.5,
                        "memory": 1024,
                    },
                },
                "details": {
                    "owner": "admin",
                    "priority": 1,
                    "active": False,
                },
                "status": "ready",
            }
            key_count += 10
            if key_count >= target_keys:
                break
        if key_count >= target_keys:
            break

    return data


def generate_ndjson_dataset(num_lines: int = 20_000) -> List[str]:
    """Генерирует список строк в формате NDJSON."""
    lines: List[str] = []
    for i in range(num_lines):
        record = {
            "id": i,
            "timestamp": 1700000000 + i,
            "user": {
                "username": f"user_{i}",
                "profile": {"role": "member", "level": (i % 10) + 1},
            },
            "payload": {
                "event": "click",
                "details": {"x": 100, "y": 200},
            },
        }
        lines.append(json.dumps(record, separators=(",", ":")))
    return lines


def run_benchmarks() -> None:
    print("=" * 65)
    print(" JSON FLATTEN PERFORMANCE BENCHMARK ")
    print("=" * 65)

    # 1. Генерация данных
    print("[1/4] Генерация тестовых наборов данных...")
    t0 = time.perf_counter()
    nested_data = generate_large_nested_dict(50_000)
    ndjson_lines = generate_ndjson_dataset(20_000)
    gen_time = time.perf_counter() - t0
    print(f"Данные готовы за {gen_time:.2f} сек.\n")

    # 2. Замер Flatten (50k ключей)
    print("[2/4] Замер операции FLATTEN (вложенный JSON)...")
    t0 = time.perf_counter()
    flattened_data = flatten(nested_data)
    flat_time = time.perf_counter() - t0
    total_flat_keys = len(flattened_data)
    flat_throughput = total_flat_keys / flat_time if flat_time > 0 else 0
    print(f"  Время:         {flat_time:.4f} сек.")
    print(f"  Ключей:        {total_flat_keys:,}")
    print(f"  Скорость:      {flat_throughput:,.0f} keys/sec\n")

    # 3. Замер Unflatten (50k ключей)
    print("[3/4] Замер операции UNFLATTEN (восстановление структуры)...")
    t0 = time.perf_counter()
    restored_data = unflatten(flattened_data)
    unflat_time = time.perf_counter() - t0
    unflat_throughput = total_flat_keys / unflat_time if unflat_time > 0 else 0
    print(f"  Время:         {unflat_time:.4f} сек.")
    print(f"  Ключей:        {total_flat_keys:,}")
    print(f"  Скорость:      {unflat_throughput:,.0f} keys/sec\n")

    # 4. Замер NDJSON Stream (20k строк)
    print("[4/4] Замер операции NDJSON STREAM (потоковое уплощение)...")
    t0 = time.perf_counter()
    consumed_count = 0
    for _ in process_ndjson_stream(ndjson_lines):
        consumed_count += 1
    stream_time = time.perf_counter() - t0
    stream_throughput = consumed_count / stream_time if stream_time > 0 else 0
    print(f"  Время:         {stream_time:.4f} сек.")
    print(f"  Строк:         {consumed_count:,}")
    print(f"  Скорость:      {stream_throughput:,.0f} lines/sec\n")

    # Итоговая сводка
    print("=" * 65)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 65)
    print(f"{'Операция':<22} | {'Объем':<14} | {'Время (с)':<10} | {'Пропускная способность':<18}")
    print("-" * 65)
    print(f"{'Flatten':<22} | {total_flat_keys:<14,} | {flat_time:<10.4f} | {f'{flat_throughput:,.0f} keys/s':<18}")
    print(f"{'Unflatten':<22} | {total_flat_keys:<14,} | {unflat_time:<10.4f} | {f'{unflat_throughput:,.0f} keys/s':<18}")
    print(f"{'NDJSON Stream':<22} | {f'{consumed_count} lines':<14} | {stream_time:<10.4f} | {f'{stream_throughput:,.0f} lines/s':<18}")
    print("=" * 65)


if __name__ == "__main__":
    run_benchmarks()
