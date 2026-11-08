

def test_a_statement_is_kept_and_a_request_is_answered():
    from camr_engine.assistant import wants_tell

    for told in ["My sister Amina moved to Nakuru last week, and her birthday is on 14 March.",
                 "Remember that rent is 28,000 from March", "Kevin's extension changed to 214",
                 "I prefer short emails", "The shop site's cart total must always round to whole shillings", "note that the water bill is due on the 15th", "Update: my rent went up to KSh 28,000 from March", "The matatu fare to Kitengela went up to KSh 120", "The shop site runs on port 8010 in production"]:
        assert wants_tell(told), told
    for asked in ["Help me plan Thursday.", "What's the capital of Kenya?", "Where does my sister live",
                  "Write a python function that adds two numbers", "Can you summarise my week",
                  "Draft a reply to Kevin", "Explain counting sort", "hello"]:
        assert not wants_tell(asked), asked


def test_a_look_up_reads_the_web_first():
    from camr_engine.assistant import wants_research

    assert wants_research("Search the web for the long rains in Kenya")
    assert wants_research("look up Mount Kenya on Wikipedia")
    assert not wants_research("Where does my sister live?") and not wants_research("My sister researches bees")
    # nothing about the person goes online by guesswork, and plain "look up" stays on the Mac
    assert not wants_research("search the web for my sister's new address")
    assert not wants_research("look up Kevin's extension") and not wants_research("research matatu fares")
