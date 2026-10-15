"""Real-HTTP Playwright app for the protocol workbench.

This factory keeps the production API/router/storage path intact while replacing
only the semantic model call with the deterministic protocol test builder.  The
data root is supplied by the test runner and is removed after browser acceptance.
"""
from __future__ import annotations

import atexit

from app.api.v2.app import create_app
from app.services.protocol_deconstruction_executor import (
    ProtocolDeconstructionExecutorConfig,
    create_protocol_deconstruction_executor,
)
from app.services.protocol_workbench_service import PROTOCOL_DECONSTRUCTION_JOB_TYPE
from app.services.protocol_workbench_service import ProtocolWorkbenchService
from app.storage.config import resolve_data_paths
from app.storage.migrate import upgrade_or_fail
from tests.v2.api.protocol_e2e_helpers import (
    build_passing_draft_json,
    page_texts_from_blocks,
)


def create_playwright_app():
    paths = resolve_data_paths()
    paths, engine, session_factory = upgrade_or_fail(paths)
    atexit.register(engine.dispose)
    executor = create_protocol_deconstruction_executor(
        ProtocolDeconstructionExecutorConfig(
            data_paths=paths,
            session_factory=session_factory,
            page_texts_builder=page_texts_from_blocks,
            draft_response_builder=build_passing_draft_json,
        )
    )
    def build_workbench_service(factory, data_paths):
        def revise(_source_input, current_draft, target_rule_code, _feedback_note):
            revised = current_draft.model_copy(deep=True)
            rule = next(
                item
                for item in revised.proposed_rules
                if item.official_code == target_rule_code
            )
            component = rule.components[0].model_copy(
                update={"title": f"{rule.components[0].title}（已按方案原文核对）"}
            )
            rule.components[0] = component
            for index, binding in enumerate(revised.component_drafts):
                if (
                    binding.proposed_component.rule_component_id
                    == component.rule_component_id
                ):
                    revised.component_drafts[index] = binding.model_copy(
                        update={"proposed_component": component}
                    )
            return revised

        return ProtocolWorkbenchService(
            factory,
            data_paths=data_paths,
            feedback_reviser=revise,
        )

    return create_app(
        data_paths=paths,
        executors={PROTOCOL_DECONSTRUCTION_JOB_TYPE: executor},
        run_runner=True,
        poll_interval=0.02,
        protocol_workbench_service_factory=build_workbench_service,
    )
