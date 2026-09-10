#!/usr/bin/env python3
"""通用且项目无关的重放 harness 命令行入口（模型无关默认路径）。

用法：

    python scripts/run_protocol_replay_harness.py --config replay-config.json
    python scripts/run_protocol_replay_harness.py --config replay-config.json --verify
    python scripts/run_protocol_replay_harness.py --verify-pack out/dir

行为：

- 默认动作 ``build``：从原始 DOCX 产品结构化链构建不可变重放包；不调用模型，
  不实例化传输层。
- ``--verify``：构建后立即对刚发布的包做确定性重放校验。
- ``--verify-pack DIR``：只校验既有重放包（只读）。
- 退出码：0 成功；2 校验不一致；3 使用/构建错误。
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.protocols.protocol_replay_harness import (  # noqa: E402
    ReplayHarnessError,
    build_protocol_replay_pack,
    load_replay_harness_config,
    replay_pack_fingerprint,
    verify_replay_pack,
)

EXIT_OK = 0
EXIT_VERIFY_MISMATCH = 2
EXIT_USAGE_OR_BUILD_ERROR = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="模型无关的协议重放 harness：原始 DOCX -> 不可变重放包。"
    )
    parser.add_argument("--config", help="重放配置 JSON 路径")
    parser.add_argument("--verify", action="store_true", help="构建后立即校验包")
    parser.add_argument(
        "--verify-pack", dest="verify_pack", help="只校验既有重放包目录（只读）"
    )
    parser.add_argument(
        "--expected-fingerprint",
        help="外部检查点记录的整包 SHA-256 指纹",
    )
    parser.add_argument(
        "--out-dir",
        help="覆盖配置中的输出目录；用于把同一只读配置重建到临时目录",
    )
    args = parser.parse_args(argv)

    if bool(args.config) == bool(args.verify_pack):
        parser.error("--config 与 --verify-pack 必须且只能提供一个")

    try:
        if args.verify_pack:
            if not args.expected_fingerprint:
                parser.error("--verify-pack 必须同时提供 --expected-fingerprint")
            out_dir = Path(args.verify_pack).resolve()
            mismatches = verify_replay_pack(
                out_dir, expected_fingerprint=args.expected_fingerprint
            )
            if mismatches:
                print(f"校验不一致（{len(mismatches)} 项）：")
                for item in mismatches:
                    print(f"  - {item}")
                return EXIT_VERIFY_MISMATCH
            print(f"校验通过：{out_dir}")
            print(f"包指纹：{replay_pack_fingerprint(out_dir)}")
            return EXIT_OK

        config = load_replay_harness_config(args.config)
        if args.out_dir:
            config = config.model_copy(update={"out_dir": args.out_dir})
        result = build_protocol_replay_pack(config)
        print(f"重放包已构建：{result.out_dir}")
        print(f"批次：{result.batch_id}")
        print(f"清单：{result.manifest_id}")
        print(f"快照：{result.snapshot_id}")
        print(f"源哈希：{result.protocol_document_sha256}")
        print(
            "单元数：blocks={blocks} manifest={manifest_units} "
            "owned={owned_units} context={context_units}".format(
                **result.unit_counts
            )
        )
        print(f"提示词 SHA-256：{result.prompt_sha256}")
        print(f"包指纹：{replay_pack_fingerprint(result.out_dir)}")
        if args.verify:
            mismatches = verify_replay_pack(
                result.out_dir,
                expected_fingerprint=replay_pack_fingerprint(result.out_dir),
            )
            if mismatches:
                print(f"校验不一致（{len(mismatches)} 项）：")
                for item in mismatches:
                    print(f"  - {item}")
                return EXIT_VERIFY_MISMATCH
            print("校验通过")
        return EXIT_OK
    except ReplayHarnessError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return EXIT_USAGE_OR_BUILD_ERROR
    except Exception as exc:  # 配置校验、合同校验等
        print(f"错误：{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_USAGE_OR_BUILD_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
