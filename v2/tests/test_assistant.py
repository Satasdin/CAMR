

def test_a_statement_is_kept_and_a_request_is_answered():
    from camr_engine.assistant import wants_tell

    for told in ["My sister Amina moved to Nakuru last week, and her birthday is on 14 March.",
                 "Remember that rent is 28,000 from March", "Kevin's extension changed to 214",
                 "I prefer short emails", "The shop site's cart total must always round to whole shillings", "note that the water bill is due on the 15th"]:
        assert wants_tell(told), told
    for asked in ["Help me plan Thursday.", "What's the capital of Kenya?", "Where does my sister live",
                  "Write a python function that adds two numbers", "Can you summarise my week",
                  "Draft a reply to Kevin", "Explain counting sort", "hello"]:
        assert not wants_tell(asked), asked


def test_a_look_up_reads_the_web_first():
    from camr_engine.assistant import wants_research

    assert wants_research("Look up the long rains in Kenya") and wants_research("research matatu fares in Nairobi")
    assert wants_research("search the web for Mount Kenya clear months")
    assert not wants_research("Where does my sister live?") and not wants_research("My sister researches bees")
