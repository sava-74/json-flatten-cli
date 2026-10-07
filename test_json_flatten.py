import json
import os
import subprocess
import sys
import tempfile
import unittest
from json_flatten import (
    collect_stats,
    flatten,
    process_ndjson_line,
    process_ndjson_stream,
    to_tabular,
    unflatten,
    write_tabular,
)


class TestJsonFlatten(unittest.TestCase):
    def test_simple_dict(self):
        data = {"a": 1, "b": 2}
        expected = {"a": 1, "b": 2}
        self.assertEqual(flatten(data), expected)

    def test_nested_dict(self):
        data = {"user": {"name": "Alice", "address": {"city": "Moscow"}}}
        expected = {"user.name": "Alice", "user.address.city": "Moscow"}
        self.assertEqual(flatten(data), expected)

    def test_nested_list(self):
        data = {"items": ["apple", "banana"]}
        expected = {"items.0": "apple", "items.1": "banana"}
        self.assertEqual(flatten(data), expected)

    def test_list_of_dicts(self):
        data = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}
        expected = {
            "users.0.id": 1,
            "users.0.name": "Alice",
            "users.1.id": 2,
            "users.1.name": "Bob",
        }
        self.assertEqual(flatten(data), expected)

    def test_custom_separator(self):
        data = {"a": {"b": 1}}
        expected = {"a/b": 1}
        self.assertEqual(flatten(data, sep="/"), expected)

    def test_empty_dict_and_list(self):
        data = {"empty_dict": {}, "empty_list": []}
        expected = {"empty_dict": {}, "empty_list": []}
        self.assertEqual(flatten(data), expected)

    def test_unflatten_roundtrip(self):
        data = {
            "user": {
                "name": "Alice",
                "roles": ["admin", "editor"],
                "profile": {"age": 30},
            }
        }
        flat = flatten(data)
        restored = unflatten(flat)
        self.assertEqual(restored, data)

    def test_max_depth_one(self):
        data = {"a": {"b": {"c": 1}}, "x": 2}
        expected = {"a": {"b": {"c": 1}}, "x": 2}
        self.assertEqual(flatten(data, max_depth=1), expected)

    def test_max_depth_two(self):
        data = {"a": {"b": {"c": 1}}, "x": 2}
        expected = {"a.b": {"c": 1}, "x": 2}
        self.assertEqual(flatten(data, max_depth=2), expected)

    def test_max_depth_with_lists(self):
        data = {"items": [{"id": 1, "name": "test"}]}
        self.assertEqual(flatten(data, max_depth=1), {"items": [{"id": 1, "name": "test"}]})
        self.assertEqual(flatten(data, max_depth=2), {"items.0": {"id": 1, "name": "test"}})
        self.assertEqual(
            flatten(data, max_depth=3),
            {"items.0.id": 1, "items.0.name": "test"},
        )

    def test_none_values(self):
        data = {"a": None, "b": {"c": None}, "list": [None, 1]}
        flat = flatten(data)
        self.assertEqual(flat, {"a": None, "b.c": None, "list.0": None, "list.1": 1})
        restored = unflatten(flat)
        self.assertEqual(restored, data)

    def test_empty_string_keys(self):
        data = {"": "root_empty", "nested": {"": "nested_empty"}}
        flat = flatten(data)
        self.assertEqual(flat, {"": "root_empty", "nested.": "nested_empty"})
        restored = unflatten(flat)
        self.assertEqual(restored, data)

    def test_special_characters_and_unicode_in_keys(self):
        data = {
            "ключ_кириллица": {"вложенный ключ": 100},
            "special!@#$%^&*()_+": "symbols",
            "emoji_🚀": {"sub_✨": True},
            "whitespace inside": [1, 2],
        }
        flat = flatten(data)
        restored = unflatten(flat)
        self.assertEqual(restored, data)

    def test_keys_with_dots_using_custom_sep(self):
        # Если ключи содержат точки, использование альтернативного разделителя (например, '/') позволяет избежать коллизий
        data = {"version.1": {"file.name.txt": "content"}}
        flat = flatten(data, sep="/")
        self.assertEqual(flat, {"version.1/file.name.txt": "content"})
        restored = unflatten(flat, sep="/")
        self.assertEqual(restored, data)

    def test_conflicting_keys_in_unflatten_no_crash(self):
        # Случай, когда один ключ является префиксом другого как примитив и объект
        flat = {"a": 1, "a.b": 2}
        restored = unflatten(flat)
        self.assertIsInstance(restored, dict)
        self.assertIn("a", restored)

    def test_unflatten_non_dict_input(self):
        self.assertEqual(unflatten(None), {})
        self.assertEqual(unflatten([]), {})
        self.assertEqual(unflatten("invalid"), {})

    def test_numeric_dict_keys_non_sequential(self):
        # Непоследовательные индексы должны оставаться словарем, а не превращаться в список
        flat = {"items.0": "first", "items.2": "third"}
        restored = unflatten(flat)
        self.assertEqual(restored, {"items": {"0": "first", "2": "third"}})


class TestJsonFlattenCLI(unittest.TestCase):
    def setUp(self):
        self.script_path = os.path.join(os.path.dirname(__file__), "json_flatten.py")

    def run_cli(self, args=None, input_data=None):
        cmd = [sys.executable, self.script_path]
        if args:
            cmd.extend(args)
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return result

    def test_cli_stdin_flatten_default(self):
        input_json = json.dumps({"a": {"b": 42}})
        res = self.run_cli(input_data=input_json)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        output_data = json.loads(res.stdout)
        self.assertEqual(output_data, {"a.b": 42})

    def test_cli_stdin_explicit_dash(self):
        input_json = json.dumps({"nested": {"value": "test"}})
        res = self.run_cli(args=["-"], input_data=input_json)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        output_data = json.loads(res.stdout)
        self.assertEqual(output_data, {"nested.value": "test"})

    def test_cli_file_input(self):
        payload = {"config": {"host": "localhost", "port": 8080}}
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as f:
            json.dump(payload, f)
            temp_path = f.name
        try:
            res = self.run_cli(args=[temp_path])
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            output_data = json.loads(res.stdout)
            self.assertEqual(output_data, {"config.host": "localhost", "config.port": 8080})
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_cli_custom_separator(self):
        input_json = json.dumps({"x": {"y": "z"}})
        res = self.run_cli(args=["-s", "/"], input_data=input_json)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        output_data = json.loads(res.stdout)
        self.assertEqual(output_data, {"x/y": "z"})

    def test_cli_unflatten_flag(self):
        input_json = json.dumps({"user.name": "Bob", "user.age": 25})
        res = self.run_cli(args=["--unflatten"], input_data=input_json)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        output_data = json.loads(res.stdout)
        self.assertEqual(output_data, {"user": {"name": "Bob", "age": 25}})

    def test_cli_unflatten_with_custom_sep(self):
        input_json = json.dumps({"level1_level2": "val"})
        res = self.run_cli(args=["-u", "-s", "_"], input_data=input_json)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        output_data = json.loads(res.stdout)
        self.assertEqual(output_data, {"level1": {"level2": "val"}})

    def test_cli_ndjson_stdin_flatten(self):
        lines = [
            json.dumps({"a": {"b": 1}}),
            json.dumps({"c": [10, 20]}),
        ]
        input_data = "\n".join(lines) + "\n"
        res = self.run_cli(args=["-n"], input_data=input_data)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        out_lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        self.assertEqual(len(out_lines), 2)
        self.assertEqual(json.loads(out_lines[0]), {"a.b": 1})
        self.assertEqual(json.loads(out_lines[1]), {"c.0": 10, "c.1": 20})

    def test_cli_ndjson_file_flatten(self):
        lines = [
            json.dumps({"user": {"name": "Alice"}}),
            json.dumps({"user": {"name": "Bob"}}),
        ]
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".ndjson") as f:
            f.write("\n".join(lines) + "\n")
            temp_path = f.name
        try:
            res = self.run_cli(args=["--ndjson", temp_path])
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            out_lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
            self.assertEqual(len(out_lines), 2)
            self.assertEqual(json.loads(out_lines[0]), {"user.name": "Alice"})
            self.assertEqual(json.loads(out_lines[1]), {"user.name": "Bob"})
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_cli_ndjson_unflatten(self):
        lines = [
            json.dumps({"user.name": "Alice", "user.age": 30}),
            json.dumps({"user.name": "Bob", "user.age": 25}),
        ]
        input_data = "\n".join(lines) + "\n"
        res = self.run_cli(args=["-n", "-u"], input_data=input_data)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        out_lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        self.assertEqual(len(out_lines), 2)
        self.assertEqual(json.loads(out_lines[0]), {"user": {"name": "Alice", "age": 30}})
        self.assertEqual(json.loads(out_lines[1]), {"user": {"name": "Bob", "age": 25}})

    def test_cli_ndjson_custom_sep(self):
        lines = [json.dumps({"a": {"b": {"c": 1}}})]
        input_data = "\n".join(lines) + "\n"
        res = self.run_cli(args=["-n", "-s", "/"], input_data=input_data)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        out_lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        self.assertEqual(out_lines[0], '{"a/b/c":1}')

    def test_cli_ndjson_compact_formatting(self):
        input_data = json.dumps({"k1": 1, "k2": 2}) + "\n"
        res = self.run_cli(args=["-n"], input_data=input_data)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        out_line = res.stdout.strip()
        self.assertNotIn(" ", out_line)

    def test_cli_max_depth(self):
        input_json = json.dumps({"a": {"b": {"c": 1}}, "x": 2})
        res = self.run_cli(args=["--max-depth", "1"], input_data=input_json)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        output_data = json.loads(res.stdout)
        self.assertEqual(output_data, {"a": {"b": {"c": 1}}, "x": 2})

        res2 = self.run_cli(args=["--max-depth", "2"], input_data=input_json)
        self.assertEqual(res2.returncode, 0, msg=res2.stderr)
        output_data2 = json.loads(res2.stdout)
        self.assertEqual(output_data2, {"a.b": {"c": 1}, "x": 2})

    def test_cli_ndjson_invalid_without_ignore_errors_fails(self):
        input_data = '{"valid": 1}\nNOT_VALID_JSON\n{"valid": 2}\n'
        res = self.run_cli(args=["-n"], input_data=input_data)
        self.assertNotEqual(res.returncode, 0)

    def test_cli_ndjson_invalid_with_ignore_errors_succeeds(self):
        input_data = '{"a": {"b": 1}}\nINVALID_ROW\n{"c": {"d": 2}}\n'
        res = self.run_cli(args=["-n", "--ignore-errors"], input_data=input_data)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Warning: skipping invalid JSON line", res.stderr)
        out_lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        self.assertEqual(len(out_lines), 2)
        self.assertEqual(json.loads(out_lines[0]), {"a.b": 1})
        self.assertEqual(json.loads(out_lines[1]), {"c.d": 2})

    def test_cli_format_csv_json_array(self):
        data = [
            {"id": 1, "user": {"name": "Alice", "city": "Moscow"}},
            {"id": 2, "user": {"name": "Bob, Jr.", "city": "London"}},
        ]
        input_data = json.dumps(data)
        res = self.run_cli(args=["--format", "csv"], input_data=input_data)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        lines = res.stdout.strip().splitlines()
        self.assertEqual(lines[0], "id,user.name,user.city")
        self.assertEqual(lines[1], "1,Alice,Moscow")
        self.assertEqual(lines[2], '2,"Bob, Jr.",London')

    def test_cli_format_tsv_json_array(self):
        data = [
            {"id": 1, "profile": {"role": "admin"}},
            {"id": 2, "profile": {"role": "editor"}},
        ]
        input_data = json.dumps(data)
        res = self.run_cli(args=["--format", "tsv"], input_data=input_data)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        lines = res.stdout.strip().splitlines()
        self.assertEqual(lines[0], "id\tprofile.role")
        self.assertEqual(lines[1], "1\tadmin")
        self.assertEqual(lines[2], "2\teditor")

    def test_cli_format_csv_ndjson(self):
        lines = [
            json.dumps({"id": 1, "meta": {"tag": "v1"}}),
            json.dumps({"id": 2, "meta": {"tag": "v2"}}),
        ]
        input_data = "\n".join(lines) + "\n"
        res = self.run_cli(args=["-n", "--format", "csv"], input_data=input_data)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        out_lines = res.stdout.strip().splitlines()
        self.assertEqual(out_lines[0], "id,meta.tag")
        self.assertEqual(out_lines[1], "1,v1")
        self.assertEqual(out_lines[2], "2,v2")

    def test_cli_format_tsv_ndjson(self):
        lines = [
            json.dumps({"a": 1, "b": {"c": 2}}),
            json.dumps({"a": 3, "b": {"c": 4}}),
        ]
        input_data = "\n".join(lines) + "\n"
        res = self.run_cli(args=["-n", "--format", "tsv"], input_data=input_data)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        out_lines = res.stdout.strip().splitlines()
        self.assertEqual(out_lines[0], "a\tb.c")
        self.assertEqual(out_lines[1], "1\t2")
        self.assertEqual(out_lines[2], "3\t4")

    def test_cli_format_csv_single_object(self):
        data = {"user": {"name": "Alice", "score": 99}}
        input_data = json.dumps(data)
        res = self.run_cli(args=["--format", "csv"], input_data=input_data)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        lines = res.stdout.strip().splitlines()
        self.assertEqual(lines[0], "user.name,user.score")
        self.assertEqual(lines[1], "Alice,99")

    def test_cli_stats_flag(self):
        data = {
            "user": {
                "name": "Alice",
                "age": 30,
                "skills": ["python", "docker"],
            }
        }
        res = self.run_cli(args=["--stats"], input_data=json.dumps(data))
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        stats = json.loads(res.stdout)
        self.assertEqual(stats["total_keys"], 4)
        self.assertEqual(stats["max_depth"], 3)
        self.assertEqual(stats["key_types"]["user.name"], ["str"])
        self.assertEqual(stats["key_types"]["user.age"], ["int"])
        self.assertEqual(stats["key_types"]["user.skills.0"], ["str"])
        self.assertEqual(stats["array_lengths"]["user.skills"], [2])

    def test_cli_schema_alias(self):
        data = {"metric": {"cpu": 15.5}}
        res = self.run_cli(args=["--schema"], input_data=json.dumps(data))
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        stats = json.loads(res.stdout)
        self.assertEqual(stats["total_keys"], 1)
        self.assertEqual(stats["max_depth"], 2)
        self.assertEqual(stats["key_types"]["metric.cpu"], ["float"])

    def test_cli_stats_ndjson(self):
        lines = [
            json.dumps({"id": 1, "val": "abc"}),
            json.dumps({"id": 2, "val": 123, "extra": True}),
        ]
        input_data = "\n".join(lines) + "\n"
        res = self.run_cli(args=["-n", "--stats"], input_data=input_data)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        stats = json.loads(res.stdout)
        self.assertEqual(stats["total_keys"], 3)
        self.assertEqual(stats["key_types"]["id"], ["int"])
        self.assertEqual(sorted(stats["key_types"]["val"]), ["int", "str"])
        self.assertEqual(stats["key_types"]["extra"], ["bool"])


class TestJsonFlattenTabularCore(unittest.TestCase):
    def test_to_tabular_csv_basic(self):
        records = [{"a.b": 1, "a.c": "text"}, {"a.b": 2, "a.c": "more"}]
        csv_str = to_tabular(records, delimiter=",")
        self.assertEqual(csv_str, "a.b,a.c\n1,text\n2,more\n")

    def test_to_tabular_tsv_basic(self):
        records = [{"k1": "val1", "k2": "val2"}]
        tsv_str = to_tabular(records, delimiter="\t")
        self.assertEqual(tsv_str, "k1\tk2\nval1\tval2\n")

    def test_to_tabular_escaping(self):
        records = [
            {"col": 'val with, comma and "quotes" and \nnewline'},
            {"col": "normal"},
        ]
        csv_str = to_tabular(records, delimiter=",")
        # csv writer should quote the first field properly
        self.assertIn('"val with, comma and ""quotes"" and \nnewline"', csv_str)

    def test_to_tabular_heterogeneous_keys(self):
        records = [
            {"a": 1},
            {"b": 2},
            {"a": 3, "b": 4, "c": 5},
        ]
        csv_str = to_tabular(records, delimiter=",")
        lines = csv_str.strip().splitlines()
        self.assertEqual(lines[0], "a,b,c")
        self.assertEqual(lines[1], "1,,")
        self.assertEqual(lines[2], ",2,")
        self.assertEqual(lines[3], "3,4,5")

    def test_to_tabular_empty(self):
        self.assertEqual(to_tabular([]), "")


class TestJsonFlattenNDJSONCore(unittest.TestCase):
    def test_process_ndjson_line_flatten(self):
        line = '{"meta": {"version": 1}}'
        res = process_ndjson_line(line)
        self.assertEqual(res, '{"meta.version":1}')

    def test_process_ndjson_line_unflatten(self):
        line = '{"meta.version":1}'
        res = process_ndjson_line(line, unflatten_mode=True)
        self.assertEqual(res, '{"meta":{"version":1}}')

    def test_process_ndjson_line_custom_sep(self):
        line = '{"meta": {"version": 1}}'
        res = process_ndjson_line(line, sep=":")
        self.assertEqual(res, '{"meta:version":1}')

    def test_process_ndjson_line_max_depth(self):
        line = '{"a": {"b": {"c": 1}}}'
        res = process_ndjson_line(line, max_depth=1)
        self.assertEqual(res, '{"a":{"b":{"c":1}}}')

    def test_process_ndjson_line_invalid_raises_by_default(self):
        with self.assertRaises(Exception):
            process_ndjson_line("BAD_JSON")

    def test_process_ndjson_line_invalid_ignore_errors(self):
        res = process_ndjson_line("BAD_JSON", ignore_errors=True)
        self.assertEqual(res, "")

    def test_process_ndjson_stream(self):
        lines = [
            '{"a": {"b": 1}}\n',
            '   \n',
            '{"c": {"d": 2}}\n',
        ]
        results = list(process_ndjson_stream(lines))
        self.assertEqual(results, ['{"a.b":1}', '{"c.d":2}'])

    def test_process_ndjson_stream_with_ignore_errors(self):
        lines = [
            '{"x": {"y": 10}}\n',
            '{corrupted line}\n',
            '{"z": 30}\n',
        ]
        results = list(process_ndjson_stream(lines, ignore_errors=True))
        self.assertEqual(results, ['{"x.y":10}', '{"z":30}'])


class TestJsonFlattenStatsCore(unittest.TestCase):
    def test_collect_stats_basic(self):
        data = {
            "user": {
                "id": 1,
                "name": "Bob",
                "active": True,
                "score": 4.5,
                "tags": ["admin", "dev"],
                "bio": None,
            }
        }
        stats = collect_stats(data)
        self.assertEqual(stats["total_keys"], 7)
        self.assertEqual(stats["max_depth"], 3)
        self.assertEqual(stats["key_types"]["user.id"], ["int"])
        self.assertEqual(stats["key_types"]["user.name"], ["str"])
        self.assertEqual(stats["key_types"]["user.active"], ["bool"])
        self.assertEqual(stats["key_types"]["user.score"], ["float"])
        self.assertEqual(stats["key_types"]["user.tags.0"], ["str"])
        self.assertEqual(stats["key_types"]["user.tags.1"], ["str"])
        self.assertEqual(stats["key_types"]["user.bio"], ["null"])
        self.assertEqual(stats["array_lengths"]["user.tags"], [2])

    def test_collect_stats_heterogeneous_records(self):
        records = [
            {"item": {"val": 10, "nums": [1]}},
            {"item": {"val": "ten", "nums": [1, 2, 3]}},
        ]
        stats = collect_stats(records)
        self.assertEqual(sorted(stats["key_types"]["item.val"]), ["int", "str"])
        self.assertEqual(stats["array_lengths"]["item.nums"], [1, 3])

    def test_collect_stats_empty(self):
        stats = collect_stats({})
        self.assertEqual(stats["total_keys"], 0)
        self.assertEqual(stats["max_depth"], 0)
        self.assertEqual(stats["key_types"], {})
        self.assertEqual(stats["array_lengths"], {})


if __name__ == "__main__":
    unittest.main()

