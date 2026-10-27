"""Traces for every agent run and room decision, sent to Application Insights when deployed.

Agent Framework emits OpenTelemetry spans for workflows, executors, agents and model calls, following the
GenAI semantic conventions (gen_ai.operation.name, gen_ai.request.model, gen_ai.usage.input_tokens and
output_tokens, ...), plus the gen_ai.client.token.usage metric. We opt in to the latest GenAI conventions so
the spans match what Microsoft Foundry's tracing view reads: the Foundry project front-room has
vu-front-room-insights connected, so every agent run shows up there with its token use.

This adds the room's own span per decision and points everything at Azure Monitor when
APPLICATIONINSIGHTS_CONNECTION_STRING is set. Locally, with no connection string, nothing is exported.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from agent_framework.observability import configure_otel_providers, get_tracer
from opentelemetry import metrics, trace

SERVICE = "front-room"


def setup() -> bool:
    connection = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection:
        return False
    from azure.monitor.opentelemetry.exporter import (
        AzureMonitorLogExporter,
        AzureMonitorMetricExporter,
        AzureMonitorTraceExporter,
    )

    configure_otel_providers(
        service_name=SERVICE,
        exporters=[
            AzureMonitorTraceExporter(connection_string=connection),
            AzureMonitorLogExporter(connection_string=connection),
            AzureMonitorMetricExporter(connection_string=connection),
        ],
        # The latest GenAI conventions, which Foundry's tracing view understands.
        otel_semconv_stability_opt_in="gen_ai_latest_experimental",
        # Fan profiles and prompts stay out of telemetry; only structure, timings, tokens and decisions.
        enable_sensitive_data=False,
    )
    return True


def flush() -> None:
    """Send what is buffered now. Long-running servers export in the background; a script that is about to
    exit (an evaluation run) calls this so its last spans aren't lost."""
    for provider in (trace.get_tracer_provider(), metrics.get_meter_provider()):
        force_flush = getattr(provider, "force_flush", None)
        if force_flush:
            force_flush()


@contextmanager
def span(name: str, **attributes: str | int | float | bool):
    with get_tracer().start_as_current_span(name) as current:
        for key, value in attributes.items():
            current.set_attribute(f"frontroom.{key}", value)
        yield current
