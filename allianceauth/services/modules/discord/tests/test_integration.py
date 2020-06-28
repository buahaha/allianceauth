"""Integration tests

Testing all components of the service, with the exception of the Discord API.

Please note that these tests require Redis and will flush it
"""
from collections import namedtuple
import logging
from unittest.mock import patch, Mock
from uuid import uuid1

from django_webtest import WebTest
from requests.exceptions import HTTPError
import requests_mock

from django.contrib.auth.models import Group, User
from django.core.cache import caches
from django.shortcuts import reverse
from django.test import TransactionTestCase, TestCase
from django.test.utils import override_settings

from allianceauth.authentication.models import State
from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils

from . import (
    TEST_GUILD_ID,
    TEST_USER_NAME, 
    TEST_USER_ID,
    TEST_USER_DISCRIMINATOR, 
    TEST_MAIN_NAME, 
    TEST_MAIN_ID, 
    MODULE_PATH,
    add_permissions_to_members,
    ROLE_ALPHA,
    ROLE_BRAVO,
    ROLE_CHARLIE,
    ROLE_MIKE,
    create_role,
    create_user_info
)
from ..discord_client.app_settings import DISCORD_API_BASE_URL
from ..models import DiscordUser

logger = logging.getLogger('allianceauth')

ROLE_MEMBER = create_role(99, 'Member')
ROLE_BLUE = create_role(98, 'Blue')

# Putting all requests to Discord into objects so we can compare them better
DiscordRequest = namedtuple('DiscordRequest', ['method', 'url'])
user_get_current_request = DiscordRequest(
    method='GET',
    url=f'{DISCORD_API_BASE_URL}users/@me'
)
guild_infos_request = DiscordRequest(
    method='GET',
    url=f'{DISCORD_API_BASE_URL}guilds/{TEST_GUILD_ID}'
)
guild_roles_request = DiscordRequest(
    method='GET',
    url=f'{DISCORD_API_BASE_URL}guilds/{TEST_GUILD_ID}/roles'
)
create_guild_role_request = DiscordRequest(
    method='POST',
    url=f'{DISCORD_API_BASE_URL}guilds/{TEST_GUILD_ID}/roles'
)
guild_member_request = DiscordRequest(
    method='GET',
    url=f'{DISCORD_API_BASE_URL}guilds/{TEST_GUILD_ID}/members/{TEST_USER_ID}'
)
add_guild_member_request = DiscordRequest(
    method='PUT',
    url=f'{DISCORD_API_BASE_URL}guilds/{TEST_GUILD_ID}/members/{TEST_USER_ID}'
)            
modify_guild_member_request = DiscordRequest(
    method='PATCH',
    url=f'{DISCORD_API_BASE_URL}guilds/{TEST_GUILD_ID}/members/{TEST_USER_ID}'
)            
remove_guild_member_request = DiscordRequest(
    method='DELETE',
    url=f'{DISCORD_API_BASE_URL}guilds/{TEST_GUILD_ID}/members/{TEST_USER_ID}'
)


def clear_cache():
    default_cache = caches['default']
    redis = default_cache.get_master_client()
    redis.flushall()
    logger.info('Cache flushed')


def reset_testdata():    
    AuthUtils.disconnect_signals()
    Group.objects.all().delete()
    User.objects.all().delete()
    State.objects.all().delete()
    EveCharacter.objects.all().delete()
    AuthUtils.connect_signals()


@patch(MODULE_PATH + '.models.DISCORD_GUILD_ID', TEST_GUILD_ID)
@override_settings(CELERY_ALWAYS_EAGER=True)
@requests_mock.Mocker()
class TestServiceFeatures(TransactionTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.maxDiff = None
                
        
    def setUp(self):
        """All tests: Given a user with member state, service permission and active Discord account"""
        clear_cache()
        reset_testdata()
        self.group_3 = Group.objects.create(name='charlie')        
        
        # States
        self.member_state = AuthUtils.get_member_state()
        self.guest_state = AuthUtils.get_guest_state()
        self.blue_state = AuthUtils.create_state("Blue", 50)
        permission = AuthUtils.get_permission_by_name('discord.access_discord')
        self.member_state.permissions.add(permission)
        self.blue_state.permissions.add(permission)

        # Test user
        self.user = AuthUtils.create_user(TEST_USER_NAME)
        self.main = AuthUtils.add_main_character_2(
            self.user, 
            TEST_MAIN_NAME, 
            TEST_MAIN_ID, 
            corp_id='2', 
            corp_name='test_corp', 
            corp_ticker='TEST',
            disconnect_signals=True
        )                
        self.member_state.member_characters.add(self.main)
        
        # verify user is a member and has an account
        self.user = User.objects.get(pk=self.user.pk)
        self.assertEqual(self.user.profile.state, self.member_state)
        
        self.discord_user = DiscordUser.objects.create(user=self.user, uid=TEST_USER_ID)
        self.assertTrue(DiscordUser.objects.user_has_account(self.user))
        
    def test_name_of_main_changes(self, requests_mocker):      
        # modify_guild_member()        
        requests_mocker.patch(modify_guild_member_request.url, status_code=204)
        
        # changing nick to trigger signals
        new_nick = f'Testnick {uuid1().hex}'[:32]
        self.user.profile.main_character.character_name = new_nick
        self.user.profile.main_character.save()

        # Need to have called modify_guild_member two times only
        # Once for sync nickname
        # Once for change of main character        
        requests_made = list()
        for r in requests_mocker.request_history:            
            requests_made.append(DiscordRequest(r.method, r.url))

        expected = [modify_guild_member_request]        
        self.assertListEqual(requests_made, expected)

    def test_name_of_main_changes_but_user_deleted(self, requests_mocker):      
        # modify_guild_member()        
        requests_mocker.patch(
            modify_guild_member_request.url, status_code=404, json={'code': 10007}
        )
        # remove_guild_member()
        requests_mocker.delete(remove_guild_member_request.url, status_code=204)
        
        # changing nick to trigger signals
        new_nick = f'Testnick {uuid1().hex}'[:32]
        self.user.profile.main_character.character_name = new_nick
        self.user.profile.main_character.save()

        # Need to have called modify_guild_member two times only
        # Once for sync nickname
        # Once for change of main character        
        requests_made = list()
        for r in requests_mocker.request_history:            
            requests_made.append(DiscordRequest(r.method, r.url))

        expected = [
            modify_guild_member_request, 
            remove_guild_member_request,            
        ]            
        self.assertListEqual(requests_made, expected)
        # self.assertFalse(DiscordUser.objects.user_has_account(self.user))

    def test_name_of_main_changes_but_user_rate_limited(
        self, requests_mocker
    ):
        # modify_guild_member()        
        requests_mocker.patch(modify_guild_member_request.url, status_code=204)
        
        # exhausting rate limit
        client = DiscordUser.objects._bot_client()
        client._redis.set(
            name=client._KEY_GLOBAL_RATE_LIMIT_REMAINING,
            value=0,
            px=2000
        )
        
        # changing nick to trigger signals
        new_nick = f'Testnick {uuid1().hex}'[:32]
        self.user.profile.main_character.character_name = new_nick
        self.user.profile.main_character.save()

        # should not have called the API
        requests_made = list()
        for r in requests_mocker.request_history:            
            requests_made.append(DiscordRequest(r.method, r.url))
        
        expected = list()  
        self.assertListEqual(requests_made, expected)
        
    def test_when_member_is_demoted_to_guest_then_his_account_is_deleted(
        self, requests_mocker
    ):        
        requests_mocker.patch(modify_guild_member_request.url, status_code=204)
        requests_mocker.delete(remove_guild_member_request.url, status_code=204)
                
        # our user is a member and has an account        
        self.assertTrue(self.user.has_perm('discord.access_discord'))
                
        # now we demote him to guest        
        self.member_state.member_characters.remove(self.main)
        
        # verify user is now guest
        self.user = User.objects.get(pk=self.user.pk)        
        self.assertEqual(self.user.profile.state, AuthUtils.get_guest_state())
        
        # verify user has no longer access to Discord and no account
        self.assertFalse(self.user.has_perm('discord.access_discord'))
        self.assertFalse(DiscordUser.objects.user_has_account(self.user))        
        
        # verify account was actually deleted from Discord server
        requests_made = [
            DiscordRequest(r.method, r.url) for r in requests_mocker.request_history
        ]                                
        self.assertIn(remove_guild_member_request, requests_made)     
        
    def test_when_member_changes_to_blue_state_then_roles_are_updated_accordingly(
        self, requests_mocker
    ):        
        # request mocks
        requests_mocker.get(
            guild_member_request.url,
            json={'user': create_user_info(),'roles': ['13', '99']}
        )     
        requests_mocker.get(
            guild_roles_request.url,
            json=[ROLE_ALPHA, ROLE_BRAVO, ROLE_MIKE, ROLE_MEMBER, ROLE_BLUE]
        )                
        requests_mocker.post(create_guild_role_request.url, json=ROLE_CHARLIE) 
        requests_mocker.patch(modify_guild_member_request.url, status_code=204)
        
        # demote user to blue state
        self.blue_state.member_characters.add(self.main)
        self.member_state.member_characters.remove(self.main)

        # verify roles for user where updated        
        roles_updated = False
        for r in requests_mocker.request_history:            
            my_request = DiscordRequest(r.method, r.url)                        
            if my_request == modify_guild_member_request and "roles" in r.json():
                roles_updated = True
                self.assertSetEqual(set(r.json()["roles"]), {13, 98})
        
        self.assertTrue(roles_updated)

    def test_adding_group_to_user_role_exists(self, requests_mocker):
        # guild_member()                
        requests_mocker.get(
            guild_member_request.url,
            json={
                'user': create_user_info(),
                'roles': ['1', '13', '99']
            }
        )        
        # guild_roles()        
        requests_mocker.get(
            guild_roles_request.url, 
            json=[ROLE_ALPHA, ROLE_BRAVO, ROLE_CHARLIE, ROLE_MIKE, ROLE_MEMBER]
        )        
        # create_guild_role()        
        requests_mocker.post(create_guild_role_request.url, json=ROLE_CHARLIE)
        # modify_guild_member()                
        requests_mocker.patch(modify_guild_member_request.url, status_code=204)
                
        # adding new group to trigger signals
        self.user.groups.add(self.group_3)        
        self.user.refresh_from_db()
        
        # compare the list of made requests with expected
        requests_made = list()
        for r in requests_mocker.request_history:            
            requests_made.append(DiscordRequest(r.method, r.url))

        expected = [
            guild_member_request,
            guild_roles_request,            
            modify_guild_member_request
        ]        
        self.assertListEqual(requests_made, expected)

    def test_adding_group_to_user_role_does_not_exist(self, requests_mocker):    
        # guild_member()                
        requests_mocker.get(
            guild_member_request.url,
            json={
                'user': {'id': str(TEST_USER_ID), 'username': TEST_MAIN_NAME},
                'roles': ['1', '13', '99']
            }
        )        
        # guild_roles()        
        requests_mocker.get(
            guild_roles_request.url, 
            json=[ROLE_ALPHA, ROLE_BRAVO, ROLE_MIKE, ROLE_MEMBER]
        )        
        # create_guild_role()        
        requests_mocker.post(create_guild_role_request.url, json=ROLE_CHARLIE)
        # modify_guild_member()                
        requests_mocker.patch(modify_guild_member_request.url, status_code=204)
                
        # adding new group to trigger signals
        self.user.groups.add(self.group_3)        
        self.user.refresh_from_db()
        
        # compare the list of made requests with expected
        requests_made = list()
        for r in requests_mocker.request_history:            
            requests_made.append(DiscordRequest(r.method, r.url))

        expected = [
            guild_member_request,
            guild_roles_request,
            create_guild_role_request,
            modify_guild_member_request
        ]        
        self.assertListEqual(requests_made, expected)
    

@override_settings(CELERY_ALWAYS_EAGER=True)
@patch(MODULE_PATH + '.managers.DISCORD_GUILD_ID', TEST_GUILD_ID)
@patch(MODULE_PATH + '.models.DISCORD_GUILD_ID', TEST_GUILD_ID)
@requests_mock.Mocker()
class StateTestCase(TestCase):
    
    def setUp(self):        
        clear_cache()
        reset_testdata()
        
        self.user = AuthUtils.create_user('test_user', disconnect_signals=True)
        AuthUtils.add_main_character(self.user, 'Perm Test Character', '99', corp_id='100', alliance_id='200',
                                     corp_name='Perm Test Corp', alliance_name='Perm Test Alliance')
        self.test_character = EveCharacter.objects.get(character_id='99')
        self.member_state = State.objects.create(
            name='Test Member',
            priority=150,
        )
        self.access_discord = AuthUtils.get_permission_by_name('discord.access_discord')
        self.member_state.permissions.add(self.access_discord)
        self.member_state.member_characters.add(self.test_character)
    
    def _add_discord_user(self):
        self.discord_user = DiscordUser.objects.create(user=self.user, uid="12345678910")

    def _refresh_user(self):
        self.user = User.objects.get(pk=self.user.pk)

    def test_perm_changes_to_higher_priority_state_creation(self, requests_mocker):
        mock_url = DiscordRequest(method='DELETE',url=f'{DISCORD_API_BASE_URL}guilds/{TEST_GUILD_ID}/members/12345678910')
        requests_mocker.delete(mock_url.url, status_code=204)
        self._add_discord_user()
        self._refresh_user()
        higher_state = State.objects.create(
            name='Higher State',
            priority=200,
        )
        self.assertIsNotNone(self.user.discord)
        higher_state.member_characters.add(self.test_character)
        self._refresh_user()
        self.assertEquals(higher_state, self.user.profile.state)
        with self.assertRaises(DiscordUser.DoesNotExist):
            self.user.discord
        higher_state.member_characters.clear()
        self._refresh_user()
        self.assertEquals(self.member_state, self.user.profile.state)
        with self.assertRaises(DiscordUser.DoesNotExist):
            self.user.discord

    def test_perm_changes_to_lower_priority_state_creation(self, requests_mocker):
        mock_url = DiscordRequest(method='DELETE',url=f'{DISCORD_API_BASE_URL}guilds/{TEST_GUILD_ID}/members/12345678910')
        requests_mocker.delete(mock_url.url, status_code=204)
        self._add_discord_user()
        self._refresh_user()
        lower_state = State.objects.create(
            name='Lower State',
            priority=125,
        )
        self.assertIsNotNone(self.user.discord)
        lower_state.member_characters.add(self.test_character)
        self._refresh_user()
        self.assertEquals(self.member_state, self.user.profile.state)
        self.member_state.member_characters.clear()
        self._refresh_user()
        self.assertEquals(lower_state, self.user.profile.state)
        with self.assertRaises(DiscordUser.DoesNotExist):
            self.user.discord
        self.member_state.member_characters.add(self.test_character)
        self._refresh_user()
        self.assertEquals(self.member_state, self.user.profile.state)
        with self.assertRaises(DiscordUser.DoesNotExist):
            self.user.discord


@patch(MODULE_PATH + '.managers.DISCORD_GUILD_ID', TEST_GUILD_ID)
@patch(MODULE_PATH + '.models.DISCORD_GUILD_ID', TEST_GUILD_ID)
@requests_mock.Mocker()
class TestUserFeatures(WebTest):
    
    def setUp(self):
        clear_cache()
        reset_testdata()
        self.member = AuthUtils.create_member(TEST_USER_NAME)
        AuthUtils.add_main_character_2(
            self.member, 
            TEST_MAIN_NAME, 
            TEST_MAIN_ID,
            disconnect_signals=True
        )
        add_permissions_to_members()
        
    @patch(MODULE_PATH + '.views.messages')    
    @patch(MODULE_PATH + '.managers.OAuth2Session')
    def test_user_activation_normal(
        self, requests_mocker, mock_OAuth2Session, mock_messages
    ): 
        # user_get_current()
        requests_mocker.get(
            user_get_current_request.url, 
            json=create_user_info(
                TEST_USER_ID, TEST_USER_NAME, TEST_USER_DISCRIMINATOR
            )
        )        
        # guild_roles()        
        requests_mocker.get(
            guild_roles_request.url, 
            json=[ROLE_ALPHA, ROLE_BRAVO, ROLE_MIKE, ROLE_MEMBER]
        )        
        # add_guild_member()
        requests_mocker.put(add_guild_member_request.url, status_code=201)
        
        authentication_code = 'auth_code'        
        oauth_url = 'https://www.example.com/oauth'
        state = ''
        mock_OAuth2Session.return_value.authorization_url.return_value = \
            oauth_url, state
        
        # login
        self.app.set_user(self.member)
        
        # click activate on the service page
        response = self.app.get(reverse('discord:activate'))
        
        # check we got a redirect to Discord OAuth        
        self.assertRedirects(
            response, expected_url=oauth_url, fetch_redirect_response=False
        )

        # simulate Discord callback
        response = self.app.get(
            reverse('discord:callback'), params={'code': authentication_code}
        )
        
        # user got a success message
        self.assertTrue(mock_messages.success.called)
        self.assertFalse(mock_messages.error.called)
        
        requests_made = list()
        for r in requests_mocker.request_history:            
            obj = DiscordRequest(r.method, r.url)            
            requests_made.append(obj)
                
        expected = [
            user_get_current_request, guild_roles_request, add_guild_member_request
        ]
        self.assertListEqual(requests_made, expected)

    @patch(MODULE_PATH + '.views.messages')    
    @patch(MODULE_PATH + '.managers.OAuth2Session')
    def test_user_activation_failed(
        self, requests_mocker, mock_OAuth2Session, mock_messages
    ): 
        # user_get_current()
        requests_mocker.get(
            user_get_current_request.url, 
            json=create_user_info(
                TEST_USER_ID, TEST_USER_NAME, TEST_USER_DISCRIMINATOR
            )
        )        
        # guild_roles()        
        requests_mocker.get(
            guild_roles_request.url, 
            json=[ROLE_ALPHA, ROLE_BRAVO, ROLE_MIKE, ROLE_MEMBER]
        )        
        # add_guild_member()
        mock_exception = HTTPError('error')
        mock_exception.response = Mock()
        mock_exception.response.status_code = 503
        requests_mocker.put(add_guild_member_request.url, exc=mock_exception)
        
        authentication_code = 'auth_code'        
        oauth_url = 'https://www.example.com/oauth'
        state = ''
        mock_OAuth2Session.return_value.authorization_url.return_value = \
            oauth_url, state
        
        # login
        self.app.set_user(self.member)
        
        # click activate on the service page
        response = self.app.get(reverse('discord:activate'))
        
        # check we got a redirect to Discord OAuth        
        self.assertRedirects(
            response, expected_url=oauth_url, fetch_redirect_response=False
        )

        # simulate Discord callback
        response = self.app.get(
            reverse('discord:callback'), params={'code': authentication_code}
        )
        
        # user got a success message
        self.assertFalse(mock_messages.success.called)
        self.assertTrue(mock_messages.error.called)
        
        requests_made = list()
        for r in requests_mocker.request_history:            
            obj = DiscordRequest(r.method, r.url)            
            requests_made.append(obj)
                
        expected = [
            user_get_current_request, guild_roles_request, add_guild_member_request
        ]
        self.assertListEqual(requests_made, expected)

    @patch(MODULE_PATH + '.views.messages')
    def test_user_deactivation_normal(self, requests_mocker, mock_messages): 
        # guild_infos()
        requests_mocker.get(
            guild_infos_request.url, json={'id': TEST_GUILD_ID, 'name': 'Test Guild'})

        # remove_guild_member()
        requests_mocker.delete(remove_guild_member_request.url, status_code=204)
        
        # user needs have an account
        DiscordUser.objects.create(user=self.member, uid=TEST_USER_ID)
        
        # login
        self.app.set_user(self.member)
        
        # click deactivate on the service page
        response = self.app.get(reverse('discord:deactivate'))
        
        # check we got a redirect to service page
        self.assertRedirects(response, expected_url=reverse('services:services'))

        # user got a success message
        self.assertTrue(mock_messages.success.called)
        self.assertFalse(mock_messages.error.called)
        
        requests_made = list()
        for r in requests_mocker.request_history:            
            obj = DiscordRequest(r.method, r.url)            
            requests_made.append(obj)
                
        expected = [remove_guild_member_request, guild_infos_request]
        self.assertListEqual(requests_made, expected)

    @patch(MODULE_PATH + '.views.messages')
    def test_user_deactivation_fails(self, requests_mocker, mock_messages): 
        # guild_infos()
        requests_mocker.get(
            guild_infos_request.url, json={'id': TEST_GUILD_ID, 'name': 'Test Guild'})

        # remove_guild_member()        
        mock_exception = HTTPError('error')
        mock_exception.response = Mock()
        mock_exception.response.status_code = 503
        requests_mocker.delete(remove_guild_member_request.url, exc=mock_exception)
        
        # user needs have an account
        DiscordUser.objects.create(user=self.member, uid=TEST_USER_ID)
        
        # login
        self.app.set_user(self.member)
        
        # click deactivate on the service page
        response = self.app.get(reverse('discord:deactivate'))
        
        # check we got a redirect to service page
        self.assertRedirects(response, expected_url=reverse('services:services'))

        # user got a success message
        self.assertFalse(mock_messages.success.called)
        self.assertTrue(mock_messages.error.called)
        
        requests_made = list()
        for r in requests_mocker.request_history:            
            obj = DiscordRequest(r.method, r.url)            
            requests_made.append(obj)
                
        expected = [remove_guild_member_request, guild_infos_request]
        self.assertListEqual(requests_made, expected)

    @patch(MODULE_PATH + '.views.messages')
    def test_user_add_new_server(self, requests_mocker, mock_messages): 
        # guild_infos()
        mock_exception = HTTPError('can not get guild info from Discord API')
        mock_exception.response = Mock()
        mock_exception.response.status_code = 440
        requests_mocker.get(guild_infos_request.url, exc=mock_exception)
        
        # login        
        self.member.is_superuser = True
        self.member.is_staff = True
        self.member.save()
        self.app.set_user(self.member)
        
        # click deactivate on the service page
        response = self.app.get(reverse('services:services'))
        
        # check we got can see the page and the "link server" button
        self.assertEqual(response.status_int, 200)
        self.assertIsNotNone(response.html.find(id='btnLinkDiscordServer'))
 