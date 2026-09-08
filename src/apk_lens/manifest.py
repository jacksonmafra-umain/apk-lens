"""Reading the facts out of a decoded manifest.

The manifest answers, without any decompilation at all:

* what the app asks the user for (permissions),
* what it exposes to other apps on the device (exported components),
* what it is allowed to look for on the device (``<queries>``),
* and how relaxed its network and backup posture is.

Exported components deserve a note. ``android:exported`` is often absent, and
then the effective value depends on whether the component has an intent filter
and on the target SDK. So the facts carry both the value *and* how it was
decided, and nothing is silently assumed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from apk_lens import axml

COMPONENT_TAGS = ("activity", "activity-alias", "service", "receiver", "provider")


@dataclass(frozen=True)
class Component:
    kind: str
    name: str
    exported: bool | None
    exported_source: str
    permission: str | None = None
    authorities: str | None = None
    actions: tuple[str, ...] = ()

    @property
    def guarded(self) -> bool:
        return bool(self.permission)

    @property
    def openly_exported(self) -> bool:
        """Exported and not behind a permission — reachable by any other app."""
        return bool(self.exported) and not self.guarded


@dataclass
class ManifestFacts:
    package: str | None = None
    version_name: str | None = None
    version_code: str | None = None
    min_sdk: str | None = None
    target_sdk: str | None = None
    compile_sdk: str | None = None
    permissions: list[str] = field(default_factory=list)
    declared_permissions: list[str] = field(default_factory=list)
    optional_permissions: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    queried_packages: list[str] = field(default_factory=list)
    queried_intents: list[str] = field(default_factory=list)
    queried_providers: list[str] = field(default_factory=list)
    metadata_keys: list[str] = field(default_factory=list)
    uses_cleartext_traffic: bool | None = None
    network_security_config: str | None = None
    allow_backup: bool | None = None
    debuggable: bool | None = None
    app_name: str | None = None

    @property
    def exported_components(self) -> list[Component]:
        return [component for component in self.components if component.exported]

    @property
    def openly_exported_components(self) -> list[Component]:
        return [component for component in self.components if component.openly_exported]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["components"] = [asdict(component) for component in self.components]
        return payload


def _flag(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() in ("true", "1")


def _name_of(element: axml.Element) -> str:
    return element.get("android:name") or element.get("name") or ""


def _actions(element: axml.Element) -> tuple[str, ...]:
    actions: list[str] = []
    for intent_filter in element.findall("intent-filter"):
        for action in intent_filter.findall("action"):
            name = _name_of(action)
            if name:
                actions.append(name)
    return tuple(actions)


def _exported(element: axml.Element, kind: str, target_sdk: str | None) -> tuple[bool | None, str]:
    """Resolve ``android:exported`` and record *why*.

    An absent value is not "false": before target SDK 31 a component with an
    intent filter defaulted to exported, and a provider defaulted to exported
    before SDK 17. Guessing silently here would turn a real finding into a
    false negative, or the reverse.
    """
    declared = _flag(element.get("android:exported") or element.get("exported"))
    if declared is not None:
        return declared, "declared in the manifest"

    has_filter = bool(element.findall("intent-filter"))
    try:
        sdk = int(target_sdk) if target_sdk else None
    except ValueError:
        sdk = None

    if kind == "provider":
        if sdk is not None and sdk >= 17:
            return False, "not declared; providers default to private on SDK 17+"
        return True, "not declared; providers defaulted to exported before SDK 17"

    if has_filter:
        if sdk is not None and sdk >= 31:
            return None, "not declared, but has an intent filter — invalid on SDK 31+"
        return True, "not declared; an intent filter made it exported before SDK 31"
    return False, "not declared and no intent filter"


def facts_from(root: axml.Element) -> ManifestFacts:
    facts = ManifestFacts(
        package=root.get("package"),
        version_name=root.get("android:versionName") or root.get("versionName"),
        version_code=root.get("android:versionCode") or root.get("versionCode"),
        compile_sdk=root.get("android:compileSdkVersion") or root.get("compileSdkVersion"),
    )

    for uses_sdk in root.findall("uses-sdk"):
        facts.min_sdk = uses_sdk.get("android:minSdkVersion") or uses_sdk.get("minSdkVersion")
        facts.target_sdk = uses_sdk.get("android:targetSdkVersion") or uses_sdk.get(
            "targetSdkVersion"
        )

    for element in root.iter():
        tag = element.tag
        name = _name_of(element)

        if tag == "uses-permission" and name or tag == "uses-permission-sdk-23" and name:
            facts.permissions.append(name)
        elif tag == "permission" and name:
            facts.declared_permissions.append(name)
        elif tag == "uses-feature" and name:
            required = _flag(element.get("android:required") or element.get("required"))
            facts.features.append(name if required is not False else f"{name} (optional)")
        elif tag == "meta-data" and name:
            # <meta-data> keys are how many SDKs are configured, so the key names
            # alone identify which vendors are bundled.
            facts.metadata_keys.append(name)
        elif tag == "application":
            facts.app_name = name or None
            facts.uses_cleartext_traffic = _flag(
                element.get("android:usesCleartextTraffic") or element.get("usesCleartextTraffic")
            )
            facts.network_security_config = element.get(
                "android:networkSecurityConfig"
            ) or element.get("networkSecurityConfig")
            facts.allow_backup = _flag(
                element.get("android:allowBackup") or element.get("allowBackup")
            )
            facts.debuggable = _flag(
                element.get("android:debuggable") or element.get("debuggable")
            )

    # <queries> declares what the app is allowed to look for on the device.
    for queries in [element for element in root.iter() if element.tag == "queries"]:
        for child in queries.children:
            name = _name_of(child)
            if child.tag == "package" and name:
                facts.queried_packages.append(name)
            elif child.tag == "provider":
                authority = child.get("android:authorities") or child.get("authorities")
                if authority:
                    facts.queried_providers.append(authority)
            elif child.tag == "intent":
                facts.queried_intents.extend(_actions(child) or ("<intent>",))

    for element in root.iter():
        if element.tag not in COMPONENT_TAGS:
            continue
        name = _name_of(element)
        if not name:
            continue
        exported, source = _exported(element, element.tag, facts.target_sdk)
        facts.components.append(
            Component(
                kind=element.tag,
                name=name,
                exported=exported,
                exported_source=source,
                permission=element.get("android:permission") or element.get("permission"),
                authorities=element.get("android:authorities") or element.get("authorities"),
                actions=_actions(element),
            )
        )

    facts.permissions = sorted(dict.fromkeys(facts.permissions))
    facts.declared_permissions = sorted(dict.fromkeys(facts.declared_permissions))
    facts.queried_packages = sorted(dict.fromkeys(facts.queried_packages))
    facts.metadata_keys = sorted(dict.fromkeys(facts.metadata_keys))
    return facts


def read(path: Path) -> ManifestFacts:
    return facts_from(axml.parse_file(path))
