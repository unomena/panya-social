from django.test import TestCase
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.comments.models import Comment
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured

from panya.models import ModelBase
from post.models import Post
from social import models
from social.models import SocialObjectPermission
        
from friends.models import Friendship

class CommentModifierTestCase(TestCase):
    def setUp(self):
        # create user and content
        self.owner = User.objects.create(username='test_user')
        self.comment = Comment(user=self.owner)
    
    def test_get_owner(self):
        self.failUnless(self.comment.get_owner(), self.owner)

class ModelBaseModifierTestCase(TestCase):
    def setUp(self):
        # create user and content
        self.owner = User.objects.create(username='test_user')
        self.modelbase = ModelBase(title='test_modelbase', owner=self.owner)
    
    def test_get_owner(self):
        self.failUnless(self.modelbase.get_owner(), self.owner)

class SocialObjectPermissionBackendTestCase(TestCase):
    fixtures=['users.json']    
    
    def setUp(self):
        # add our backend if not already there
        self.backend_str = 'social.backends.SocialObjectPermissionBackend'
        if self.backend_str not in settings.AUTHENTICATION_BACKENDS:
            settings.AUTHENTICATION_BACKENDS = settings.AUTHENTICATION_BACKENDS + (self.backend_str,)

        # create some users and content
        self.owner = User.objects.create(username='target_user')
        self.intermediate_user = User.objects.create(username='intermediate_user')
        self.requesting_user = User.objects.create(username='requesting_user')
        self.post = Post.objects.create(title='Post Title', owner=self.owner)

    def test_has_perm(self):
        # if no permissions are set fallback to default
        SocialObjectPermission.objects.all().delete()
        # default of nobody should always be false
        settings.DEFAULT_SOCIAL_PERMISSION_GROUP = 0    # Nobody
        self.failIf(self.requesting_user.has_perm(perm='view', obj=self.post))
        # default of everyone should always be true
        settings.DEFAULT_SOCIAL_PERMISSION_GROUP = 1    # Everybody
        self.failUnless(self.requesting_user.has_perm(perm='view', obj=self.post))
        
        # default of friend should be true if requesting user is a friend
        settings.DEFAULT_SOCIAL_PERMISSION_GROUP = 2    # Friends
        direct_friendship = Friendship(to_user=self.requesting_user, from_user=self.owner)
        direct_friendship.save()
        self.failUnless(self.requesting_user.has_perm(perm='view', obj=self.post))
        direct_friendship.delete()
        
        # default of friends of friends should be true if requesting user is a friend of a friend
        settings.DEFAULT_SOCIAL_PERMISSION_GROUP = 3    # Friends of Friends
        Friendship(to_user = self.intermediate_user, from_user=self.owner).save()
        indirect_friendship = Friendship(to_user = self.requesting_user, from_user=self.intermediate_user)
        indirect_friendship.save()
        self.failUnless(self.requesting_user.has_perm(perm='view', obj=self.post))
        indirect_friendship.delete()

        # if no default is set and no perms are found raise a conf error
        del settings.DEFAULT_SOCIAL_PERMISSION_GROUP
        SocialObjectPermission.objects.all().delete()
        self.failUnlessRaises(ImproperlyConfigured, self.requesting_user.has_perm, perm='view', obj=self.post)

        # if a permission does exist use it to determine access
        # nobody perm should always be false
        nobody_perm = SocialObjectPermission(user=self.owner, can_view=True, social_group=0, content_type=ContentType.objects.get_for_model(self.post))
        nobody_perm.save()
        self.failIf(self.requesting_user.has_perm(perm='view', obj=self.post))
        nobody_perm.delete()
        
        # everyone perm should always be true
        everyone_perm = SocialObjectPermission(user=self.owner, can_view=True, social_group=1, content_type=ContentType.objects.get_for_model(self.post))
        everyone_perm.save()
        self.failUnless(self.requesting_user.has_perm(perm='view', obj=self.post))
        everyone_perm.delete()

        # permission takes priority by group id
        # hence nobody takes priority over everyone since it has a lower group number
        nobody_perm = SocialObjectPermission(user=self.owner, can_view=True, social_group=0, content_type=ContentType.objects.get_for_model(self.post))
        nobody_perm.save()
        everyone_perm = SocialObjectPermission(user=self.owner, can_view=True, social_group=1, content_type=ContentType.objects.get_for_model(self.post))
        everyone_perm.save()
        self.failIf(self.requesting_user.has_perm(perm='view', obj=self.post))
        
    def test_is_member_everyone(self):
        # always retrun true
        self.failUnless(models.is_member_everyone(self.owner, self.requesting_user))
    
    def test_is_member_nobody(self):
        # always retrun false
        self.failIf(models.is_member_nobody(self.owner, self.requesting_user))
    
    def test_is_member_friends(self):
        # return false if requesting user is not a friend
        self.failIf(models.is_member_friends(self.owner, self.requesting_user))
        
        # return true if requesting user is a friends
        Friendship(to_user=self.requesting_user, from_user=self.owner).save()
        self.failUnless(models.is_member_friends(self.owner, self.requesting_user))
    
    def test_is_member_friends_of_friends(self):
        # return true if requesting user is a friend
        direct_friendship = Friendship(to_user=self.requesting_user, from_user=self.owner)
        direct_friendship.save()
        self.failUnless(models.is_member_friends_of_friends(self.owner, self.requesting_user))
        direct_friendship.delete()
        
        # return true if requesting user is a friend of a friend
        Friendship(to_user = self.intermediate_user, from_user=self.owner).save()
        indirect_friendship = Friendship(to_user = self.requesting_user, from_user=self.intermediate_user)
        indirect_friendship.save()
        self.failUnless(models.is_member_friends_of_friends(self.owner, self.requesting_user))
        indirect_friendship.delete()
        
        # return false if requesting user is not a friend, nor a friend of a friend
        self.failIf(models.is_member_friends_of_friends(self.owner, self.requesting_user))
