from rest_framework import serializers
from .models import Project, Task
from django.contrib.auth.models import User

class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'email']

class ProjectSerializer(serializers.ModelSerializer):

    members = UserSimpleSerializer(many=True, read_only=True)


    class Meta:
        model = Project
        fields = ['id', 'title', 'description', 'created_by', 'members']
        extra_kwargs = {
            'description': {'required': False, 'allow_blank': True}
        }
        read_only_fields = ['created_by' ,'members'] # Isse user override nahi kar payega

    def get_is_admin(self, obj):
        # Request se current user uthayein
        user = self.context.get('request').user
        # Check karein ki kya user hi creator hai
        return obj.created_by == user



class TaskSerializer(serializers.ModelSerializer):
    # Assigned user ka naam dikhane ke liye
    assigned_to_name = serializers.ReadOnlyField(source='assigned_to.username')

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'status',
            'priority', 'due_date', 'assigned_to', 'assigned_to_name'
        ]