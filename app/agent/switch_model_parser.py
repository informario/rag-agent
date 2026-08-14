"""Evidence-first extraction of switch specifications from PDF slices."""

from collections.abc import Iterable

from app.utils.llm import get_llm


prompt = r'''
You are extracting hardware facts from one PDF slice of a network-switch
datasheet. The selected switch-model node title is the authoritative model
identity. Return exactly one JSON object for that selected model.

The object must include:
- model_name: copy the supplied selected switch-model node title exactly.
  Never substitute a part number, component heading, AC/DC power configuration,
  fan-box name, or a different model mentioned in the PDF slice.

Include these fields only when the source explicitly supports their value:
- configuration: "modular" or "fixed".
- height_ru: JSON number, in rack units (RU/U).
- depth_cm: JSON number, the physical modular switch body depth in centimetres. You
  may convert an explicit millimetre value by dividing by 10.
- linecard_slots: JSON integer. LPU/line-processing-unit slots count only when
  the source explicitly identifies them as LPU/linecard slots.
- switch_fabric_slots: JSON integer for SFU/switch-fabric slots.
- fan_trays: JSON integer for modular switch fan trays/modules/slots.
- power_supplies_amount: JSON integer for modular switch power-supply/module slots.
- operating_temperature_celsius: an object exactly shaped as
  {"min": <number>, "max": <number>}. Use an operating range, not storage or
  transport temperature.
- max_power_consumption_w: JSON number for a value explicitly labelled maximum
  power consumption. Do NOT substitute maximum output power, typical power, or
  a calculated total.
- max_throughput: the explicitly stated maximum switching/forwarding capacity,
  preserved as a concise string with its source unit (for example, "256 Tbps").
- throughput_per_slot: the explicitly stated per-slot capacity, preserved as a
  concise string with its source unit.
- chipset: exact chipset/ASIC name only when explicitly named.
- macsec: "Yes" only for explicit support and "No" only for an explicit statement
  that it is unsupported. An omitted MACsec mention is not "No".

Non-negotiable anti-hallucination rules:
1. Never use outside knowledge, a model-number convention, a diagram count,
   nearby product information, or a value from a different variant.
2. Do not infer one requested field from another (for example, do not turn LPU
   slots into a modular classification or maximum output power into consumption).
3. When source wording is ambiguous, incomplete, applies to more than one
   variant, or conflicts, omit the field. Do not resolve ambiguity by guessing.
4. Omit unavailable fields; never emit null, "unknown", 0, an empty string, or
   that entire object.
If no specification fields are supported, still return the object containing
only model_name.
5. Specification values must be contained in the PDF slice. The selected node
   title is only the model identity; do not derive any specification from it.

Return ONLY the valid JSON object. No markdown, explanation, code fence, or
extra keys.
'''


SPEC_FIELDS = frozenset({
    "model_name",
    "configuration",
    "height_ru",
    "depth_cm",
    "linecard_slots",
    "switch_fabric_slots",
    "fan_trays",
    "power_supplies_amount",
    "operating_temperature_celsius",
    "max_power_consumption_w",
    "max_throughput",
    "throughput_per_slot",
    "chipset",
    "macsec",
})


class SwitchModelRegistry:
    """Keeps only non-empty, schema-safe switch-model records.

    The registry intentionally does not manufacture defaults for missing data.
    """

    def __init__(self):
        self._records: dict[str, dict] = {}

    @staticmethod
    def _is_valid_temperature(value) -> bool:
        return (
            isinstance(value, dict)
            and set(value) == {"min", "max"}
            and isinstance(value["min"], (int, float))
            and not isinstance(value["min"], bool)
            and isinstance(value["max"], (int, float))
            and not isinstance(value["max"], bool)
            and value["min"] <= value["max"]
        )

    @classmethod
    def _clean(cls, record: object) -> dict | None:
        if not isinstance(record, dict):
            return None
        name = record.get("model_name")
        if not isinstance(name, str) or not name.strip():
            return None

        cleaned = {"model_name": name.strip()}
        for key in SPEC_FIELDS:
            value = record.get(key)
            if value is None:
                continue
            if key == "configuration" and value in {"modular", "fixed"}:
                cleaned[key] = value
            elif key == "macsec" and value in {"Yes", "No"}:
                cleaned[key] = value
            elif key == "operating_temperature_celsius" and cls._is_valid_temperature(value):
                cleaned[key] = value
            elif key in {
                "height_ru", "depth_cm", "max_power_consumption_w",
            } and isinstance(value, (int, float)) and not isinstance(value, bool):
                cleaned[key] = value
            elif key in {
                "linecard_slots", "switch_fabric_slots", "fan_trays", "power_supplies_amount",
            } and isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                cleaned[key] = value
            elif key in {"max_throughput", "throughput_per_slot", "chipset"} and isinstance(value, str) and value.strip():
                cleaned[key] = value.strip()

        return cleaned

    def add_many(self, records: Iterable[object]) -> int:
        """Add valid records; conflicting duplicate names are left untouched."""
        added = 0
        for record in records:
            cleaned = self._clean(record)
            if not cleaned:
                continue
            name = cleaned["model_name"]
            existing = self._records.get(name)
            if existing is None:
                self._records[name] = cleaned
                added += 1
            elif existing == cleaned:
                continue
            else:
                # Two incompatible records for one switch model cannot safely be
                # merged without knowing which source/variant is authoritative.
                continue
        return added

    def to_list(self) -> list[dict]:
        return [self._records[name] for name in sorted(self._records)]


def parse_switch_models(text: str, node_title: str) -> str:
    """Ask the configured LLM for source-grounded switch-model records."""
    return get_llm().complete(
        f"{prompt}\n\nSelected switch-model node title: {node_title}\n\nPDF slice:\n{text}"
    ).text
