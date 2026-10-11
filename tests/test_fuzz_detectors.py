import json

from fuzz.detectors import ProtocolObserver, Severity, request_signatures


def observe(*lines):
    observer = ProtocolObserver()
    observer.observe("\n".join([">battle-gen9randombattle-1", *lines]))
    return {(f.severity, f.kind, f.key) for f in observer.findings}


class TestProtocolObserver:
    def test_parsed_message_has_no_findings(self):
        assert (
            observe(
                "|move|p1a: Pikachu|Thunderbolt|p2a: Pidgey",
                "|-damage|p2a: Pidgey|0 fnt|[from] item: Life Orb",
            )
            == set()
        )

    def test_ignored_message_has_no_findings(self):
        assert observe("|-hint|Some hint", "|t:|123", "|") == set()

    def test_unrecognized_message_type_is_drift(self):
        assert observe("|-newthing|p1a: Pikachu") == {
            (Severity.DRIFT, "unrecognized-message", "-newthing")
        }

    def test_known_unhandled_message_type_is_known_gap(self):
        assert observe("|-copyboost|p1a: Pikachu|p2a: Pidgey") == {
            (Severity.KNOWN_GAP, "unhandled-message", "-copyboost")
        }

    def test_unrecognized_kwarg_is_drift(self):
        assert observe("|-damage|p1a: Pikachu|50/100|[newkwarg] thing") == {
            (Severity.DRIFT, "unrecognized-kwarg", "-damage [newkwarg]")
        }

    def test_unrecognized_effect_prefix_is_drift(self):
        assert observe("|-start|p1a: Pikachu|newprefix: Thing") == {
            (Severity.DRIFT, "unrecognized-effect-prefix", "-start newprefix:")
        }

    def test_unrecognized_effect_prefix_in_from_is_drift(self):
        assert observe("|-heal|p1a: Pikachu|50/100|[from] newprefix: Thing") == {
            (Severity.DRIFT, "unrecognized-effect-prefix", "-heal newprefix:")
        }

    def test_parse_exception_is_error(self):
        assert observe("|-damage|not an ident|50/100") == {
            (Severity.ERROR, "parse-exception", "-damage: ValueError")
        }

    def test_invalid_choice_is_error(self):
        assert observe(
            "|error|[Invalid choice] Can't move: Your Pikachu doesn't have a move 9"
        ) == {(Severity.ERROR, "invalid-choice", "[Invalid choice] Can't move")}

    def test_free_text_is_not_checked_for_kwargs(self):
        assert observe("|-message|[notakwarg] text | with a pipe") == set()

    def test_findings_are_counted(self):
        observer = ProtocolObserver()
        observer.observe("|-newthing|p1a: Pikachu\n|-newthing|p1a: Pikachu")
        assert [f.count for f in observer.findings] == [2]

    def test_signatures(self):
        observer = ProtocolObserver()
        observer.observe(
            "|-damage|p1a: Pikachu|50/100|[from] item: Life Orb\n|-damage|p1a: Pikachu|25/100"
        )
        assert observer.signatures == {"-damage/2/from": 1, "-damage/2/": 1}


def test_request_signatures():
    request = {"rqid": 1, "side": {"pokemon": [{"ident": "p1: A"}, {"ident": "p1: B"}]}}
    assert request_signatures(json.loads(json.dumps(request))) == {
        "request",
        "request.rqid",
        "request.side",
        "request.side.pokemon[]",
        "request.side.pokemon[].ident",
    }
