"""
test_ratmama.py - Tests for the Ratmama.py

Tests the parsing facilities for ratsignals

Copyright (c) 2018 The Fuel Rat Mischief,
All rights reserved.

Licensed under the BSD 3-Clause License.

See LICENSE.md
"""

import pytest
from Modules.rat_board import RatBoard
from tests.mock_callables import AsyncCallableMock
from Modules.context import Context
import Modules.RatMama as RatMama
from Modules.rat_rescue import Platforms
from Modules.rat_rescue import Rescue
import config

pytestmark = [pytest.mark.ratsignal_parse, pytest.mark.asyncio]


class TestRSignal(object):
    rat_board: RatBoard

    @pytest.fixture(scope="class", autouse=True)
    def setUp(self, galaxy_fx):
        RatMama.Galaxy = galaxy_fx

    @pytest.mark.parametrize("nick", config.config["ratsignal_parser"]["announcer_nicks"])
    async def test_ratmama_wrong_platform(self, context_channel_fx: Context,
                                          monkeypatch,
                                          nick,
                                          caplog
                                          ):
        """
        Tests, that the parser does not implode upon being given a wrong platform by RatMama
        """
        words = "Incoming Client: Ajdacho - System: ANGRBONII - "\
                "Platform: Switch - O2: OK - Language: Polish (pl-PL)"
        split_words = words.split(" ")
        monkeypatch.setattr(context_channel_fx, '_words_eol',
                            [" ".join(v) for v in
                             [split_words[k:] for k, v in enumerate(split_words)]
                             ]
                            )

        # now we just set the nickname to the allowed on
        monkeypatch.setattr(context_channel_fx._user, '_nickname', f"{nick}")
        # and fire away!
        await RatMama.handle_ratmama_announcement(context_channel_fx)
        assert f"Got unknown platform from {nick}: Switch" in [rec.message for rec in caplog.records]

    @pytest.mark.parametrize("nick", config.config["ratsignal_parser"]["announcer_nicks"])
    async def test_ratmama_arrival_and_rearrival(self,
                                                 async_callable_fx: AsyncCallableMock,
                                                 context_channel_fx: Context,
                                                 monkeypatch,
                                                 nick
                                                 ):
        """
        Tests the RSignal announcement as well as the reconnect message.
        """
        # use our own function for reply so we can track it's calls
        monkeypatch.setattr(context_channel_fx, 'reply', async_callable_fx)
        # and give it our own board, again, for tracking purposes
        rat_board = context_channel_fx.bot.board

        # set the message to a valid announcement
        words = "Incoming Client: Ajdacho - System: EORLD PRI QI-Z D1-4302 - "\
                "Platform: PC - O2: OK - Language: Polish (pl-PL)"
        split_words = words.split(" ")
        monkeypatch.setattr(context_channel_fx, '_words_eol',
                            [" ".join(v) for v in
                             [split_words[k:] for k, v in enumerate(split_words)]
                             ]
                            )

        # now we just set the nickname to the allowed on
        monkeypatch.setattr(context_channel_fx._user, '_nickname', f"{nick}")
        # and fire away!
        await RatMama.handle_ratmama_announcement(context_channel_fx)
        # lets grab the result!
        rescue: Rescue = rat_board.find_by_name("Ajdacho")
        # remember the index
        index = rescue.board_index
        # and assert, the right announcement was to be send
        print(async_callable_fx.calls)
        assert async_callable_fx.was_called_with(
            f"RATSIGNAL - CMDR Ajdacho - "
            f"Reported System: EORLD PRI QI-Z D1-4302 (6272.85 LY from SAGITTARIUS A*) - "
            f"Platform: PC - "
            f"O2: OK - "
            f"Language: Polish (pl-PL) (Case #{index}) (PC_SIGNAL)")

        # assert rescue details are as expected
        assert rescue.client.casefold() == "ajdacho"
        assert rescue.system.casefold() == "eorld pri qi-z d1-4302"
        assert rescue.platform == Platforms.PC
        assert not rescue.code_red
        assert rescue.lang_id.casefold() == "pl"

        # fire it again
        await RatMama.handle_ratmama_announcement(context_channel_fx)
        # and assure it recognized it as a reconnect
        assert async_callable_fx.was_called_with(
            f"Ajdacho has reconnected! Case #{index}"
        )

    @pytest.mark.parametrize("nick", config.config["ratsignal_parser"]["announcer_nicks"])
    async def test_reconnect_with_changes(self,
                                          async_callable_fx: AsyncCallableMock,
                                          context_channel_fx: Context,
                                          monkeypatch,
                                          nick
                                          ):
        """
        Tests the recognition of changes and the emission of the associated message.
        Tests a single case only
        """
        # set up all our tracking
        monkeypatch.setattr(context_channel_fx, 'reply', async_callable_fx)
        rat_board = context_channel_fx.bot.board

        # set our first message
        words = "Incoming Client: Ajdacho - System: EORLD PRI QI-Z D1-4302 - Platform: PC - O2: OK - " \
                "Language: Polish (pl-PL)"
        split_words = words.split(" ")
        monkeypatch.setattr(context_channel_fx, '_words_eol',
                            [" ".join(v) for v in
                             [split_words[k:] for k, v in enumerate(split_words)]
                             ]
                            )

        # set the nickname of the announcer
        monkeypatch.setattr(context_channel_fx._user, '_nickname', nick)
        # and have it processed
        await RatMama.handle_ratmama_announcement(context_channel_fx)
        # remember the index (is important later!)
        index = rat_board.find_by_name("Ajdacho").board_index

        # prepare second announcement, this one has different details,
        # but is from the same commander
        words = "Incoming Client: Ajdacho - System: ANGRBONII - Platform: XB - O2: NOT OK - " \
                "Language: Polish (pl-PL)"
        split_words = words.split(" ")
        monkeypatch.setattr(context_channel_fx, '_words_eol',
                            [" ".join(v) for v in
                             [split_words[k:] for k, v in enumerate(split_words)]
                             ]
                            )

        # and handle it
        await RatMama.handle_ratmama_announcement(context_channel_fx)
        # make sure it recognized it as a reconnect
        assert async_callable_fx.was_called_with(
            f"Ajdacho has reconnected! Case #{index}"
        )

        # as well as the fact some stuff changes
        assert async_callable_fx.was_called_with(
            "System changed! Platform changed! O2 Status changed, it is now CODE RED!"
        )

    async def test_no_action_on_wrong_nick(self, async_callable_fx: AsyncCallableMock,
                                           context_channel_fx: Context,
                                           monkeypatch
                                           ):
        """
        Tests, that a wrong nickname has no associated action when handed to the RatMama handler.
        """
        # use a valid announcement
        words = "Incoming Client: Ajdacho - System: H - Platform: XB - "\
                "O2: OK - Language: Polish (pl-PL)"
        split_words = words.split(" ")
        monkeypatch.setattr(context_channel_fx, '_words_eol',
                            [" ".join(v) for v in
                             [split_words[k:] for k, v in enumerate(split_words)]
                             ]
                            )

        # with an invalid nickname
        monkeypatch.setattr(context_channel_fx._user, '_nickname', "MasterLoon")
        # have it licked by the handler
        await RatMama.handle_ratmama_announcement(context_channel_fx)
        # make sure it tasted awful
        assert not async_callable_fx.was_called

    @pytest.mark.parametrize("sep", [',', ';', '|', '-'])
    @pytest.mark.parametrize("platform_str, platform",
                             [("pc", Platforms.PC), ("ps", Platforms.PS), ("ps4", Platforms.PS),
                              ("playstation", Platforms.PS), ("playstation4", Platforms.PS),
                              ("Playstation 4", Platforms.PS), ("xb", Platforms.XB),
                              ("xb1", Platforms.XB), ("xbox", Platforms.XB),
                              ("xbox one", Platforms.XB)
                              ]
                             )
    @pytest.mark.parametrize("system, expected_distance, expected_landmark_name",
                             [("ANGRBONII", 14.56, "FUELUM"),
                              ("CHUA EOHN CT-F D12-2", 6413.86, "BEAGLE POINT"),
                              ("Fuelum", 0, "FUELUM")
                              ]
                             )
    @pytest.mark.parametrize("nick", ["Absolver", "Numerlor", "A_Cheesy_Potato[with_tags]"])
    @pytest.mark.parametrize("cr_string, cr_expected", [("OK", False), ("NOT OK", True)])
    async def test_manual_rsig_handler(self,
                                       async_callable_fx: AsyncCallableMock,
                                       context_channel_fx: Context,
                                       monkeypatch,
                                       sep: chr,
                                       platform_str: str,
                                       platform: Platforms,
                                       system: str,
                                       expected_distance: float,
                                       expected_landmark_name: str,
                                       nick: str,
                                       cr_string: str,
                                       cr_expected: bool
                                       ):
        """
        Tests with multiple cases, that the parser recognized the case details
        and creates an appropriate rescue
        """

        # again, tracking stuff needs to be set up
        monkeypatch.setattr(context_channel_fx, 'reply', async_callable_fx)
        rat_board = context_channel_fx.bot.board

        # give us a message
        monkeypatch.setattr(context_channel_fx, '_words_eol',
                            [f"ratsignal {system}{sep}{platform_str}{sep}O2 {cr_string} "]
                            )

        # and a nickname
        monkeypatch.setattr(context_channel_fx._user, '_nickname', nick)
        # throw it into the magic black box
        await RatMama.handle_ratsignal(context_channel_fx)
        # and remember the result
        case = rat_board.find_by_name(nick.split("[")[0])

        # assert all details are as expected
        assert case is not None
        assert case.platform == platform
        assert case.system.casefold() == system.casefold()
        assert case.irc_nickname.casefold() == nick.casefold()
        assert case.code_red == cr_expected

        dist_str = f", {expected_distance} LY from {expected_landmark_name}" if \
        system.casefold() != expected_landmark_name.casefold() else ""

        assert async_callable_fx.was_called_with(
            f"Case created for {nick} on {platform.name} in {system}"
            f"{dist_str}. "
            f"{'O2 status is okay' if not cr_expected else 'This is a CR!'}"
            f" - {platform.name.upper()}_SIGNAL"
        )

        # who needs flash when they can have cleanse?
        rat_board.clear_board()
        async_callable_fx.reset()

        # now lets get a bit more mean with the message
        monkeypatch.setattr(context_channel_fx, '_words_eol',
                            [f"Ratsignal RaTsIgNaL{sep} RATSIGNAL ratsIGnal{system}{sep} "
                             f"{platform_str}ratsignal{sep} o2 {cr_string} please help! Ratsignal!"]
                            )

        # ensure who is the case summoner
        monkeypatch.setattr(context_channel_fx._user, '_nickname', nick)
        # throw it into the abyss
        await RatMama.handle_ratsignal(context_channel_fx)
        # catch the soul
        case = rat_board.find_by_name(nick.split("[")[0])

        # make sure we threw the right person into the abyss earlier
        assert case is not None
        assert case.platform == platform
        assert case.system.casefold() == system.casefold()
        assert case.irc_nickname.casefold() == nick.casefold()
        assert case.code_red == cr_expected

        assert async_callable_fx.was_called_with(
            f"Case created for {nick} on {platform.name} in {system}"
            f"{dist_str}. "
            f"{'O2 status is okay' if not cr_expected else 'This is a CR!'}"
            f" - {platform.name.upper()}_SIGNAL"
        )

    async def test_you_already_sent(self, async_callable_fx: AsyncCallableMock,
                                       bot_fx
                                    ):
        """
        Tests, that upon sending a ratsignal, the client will be nicely told that they already
        sent a signal
        """
        context = await Context.from_message(bot_fx, "#snickers", "unit_test", "ratsignal")
        context.reply = async_callable_fx
        await RatMama.handle_ratsignal(context)
        await RatMama.handle_ratsignal(context)
        assert async_callable_fx.was_called_with(
            "You already sent a signal, please be patient while a dispatch is underway."
        )