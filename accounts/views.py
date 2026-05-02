from http.client import responses

from django.shortcuts import render
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Count, Q

from .models import Project, Task
from .serializers import ProjectSerializer, TaskSerializer


# Create your views here.


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        data = request.data
        print(data)

        # 1. Sabhi fields extract karna
        student_name = data.get('student_name')
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        # Pehle manual check karein username ke liye
        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already taken"}, status=status.HTTP_400_BAD_REQUEST)

        # 3. User Create karna
        try:
            user = User.objects.create_user(
                first_name=student_name,  # Student Name ko first_name mein store kar rahe hain
                username=username,
                password=password,
                email=email
            )
            return Response({"msg": "User Created Successfully"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(f"ERROR DURING SIGNUP: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class Login(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)

        if user is not None:
            token = get_tokens_for_user(user)
            response = Response({"msg": "Login Success"}, status=status.HTTP_200_OK)

            response.set_cookie(
                key='access_token',
                value=token['access'],
                httponly=True,
                secure=True, # true if production
                samesite='None',
                # max_age=86400,
                path='/'
            )
            return response
        else:
            return Response({"msg": "Invalid Credential"}, status=status.HTTP_401_UNAUTHORIZED)

class Logout(APIView):
    def post(self, request):
        response = Response({"msg": "Logout Success"}, status=status.HTTP_200_OK)
        response.delete_cookie(
            'access_token',
            path = '/',
            samesite = 'None',
        )
        return response

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@authentication_classes([])
def check_username(request):
    username = request.data.get('username')

    if not username:
        return Response({"available": False, "error": "Username cannot be empty"}, status=200)

    # Database check
    exists = User.objects.filter(username__iexact=username).exists()


    if exists:
        return Response({"available": False, "error": "Username already taken"}, status=200)
    else:
        return Response({"available": True, "msg": "Username available"}, status=200)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_auth_status(request):
    # Agar request yahan tak pahunchi, matlab JWT cookie valid hai
    return Response({
        "user_id": request.user.id,
        "is_logged_in": True,
        "username": request.user.username,
        "email": request.user.email,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    user = request.user

    data = {
        "username": user.username,
        "first_name": user.first_name,
        "email": user.email,
    }

    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_project(request):

    serializer = ProjectSerializer(data=request.data)

    if serializer.is_valid():
        project = serializer.save(created_by=request.user)

        project.members.add(request.user)

        return Response({"msg":"Project Created Successfull","project_id": project.id}, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_project(request, pk):
    try:
        project = Project.objects.get(pk=pk)

        # Security: Sirf Admin delete kar sake
        if project.created_by != request.user:
            return Response({"error": "Only the Admin can delete this project"}, status=403)

        project.delete()
        return Response({"msg": "Project deleted successfully"}, status=200)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def show_project(request):

    project = Project.objects.filter(members=request.user).distinct()

    serializer = ProjectSerializer(project, many=True, context={'request': request})

    # Serializer ka data ab ek list of dictionaries hai
    project_list = serializer.data

    # Har project par loop chala kar check karein ki login user uska admin hai ya nahi
    for i in range(len(project)):
        # original queryset (projects) se comparison karke dynamic field add karein
        project_list[i]['is_admin'] = (project[i].created_by == request.user)

    return Response(project_list)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dashboard_stats(request):
    user = request.user
    now = timezone.now()

    # Sirf wahi projects jinme user member hai
    user_projects = Project.objects.filter(members=user)

    # User se related saare tasks (Total)
    all_tasks = Task.objects.filter(project__in=user_projects)

    stats = {
        "total_tasks": all_tasks.count(),

        # Tasks by status
        "status_counts": {
            "todo": all_tasks.filter(status='To Do').count(),
            "in_progress": all_tasks.filter(status='In Progress').count(),
            "done": all_tasks.filter(status='Done').count(),
        },

        # Overdue tasks (Due date nikal gayi aur status 'Done' nahi hai)
        "overdue_tasks": all_tasks.filter(
            due_date__lt=now.date()
        ).exclude(status='Done').count(),

        # Tasks per user (Project members ki summary)
        "tasks_per_user": list(all_tasks.values('assigned_to__username')
                               .annotate(count=Count('id'))
                               .order_by('-count'))
    }

    return Response(stats)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_project_detail(request, pk):
    try:
        # Project ko uski ID se fetch karein
        project = Project.objects.prefetch_related('members').get(pk=pk)

        # Check karein ki user member hai ya nahi
        if not project.members.filter(id=request.user.id).exists():
            return Response({"error": "Access Denied"}, status=403)

        serializer = ProjectSerializer(project, context={'request': request})
        return Response(serializer.data)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=404)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_members(request, pk):
    try:
        project = Project.objects.get(pk=pk)

        # 1 sirf admin add kar sake
        if project.created_by != request.user:
            return Response({"error": "Access Denied"}, status=403)


        # reqird email
        email = request.data.get('email')
        if not email:
            return Response({"error": "Email cannot be empty"}, status=400)

        # 3. find user
        try:
            user_to_add = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User with this email not found"}, status=404)

        #4. member can add project
        project.members.add(user_to_add)
        return Response({'msg': f"User {user_to_add.username} added successfully!"})
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_task(request):
    project_id = request.data.get('project')
    try:
        project = Project.objects.get(id=project_id)

        # Security: Check karein ki user is project ka member hai ya nahi
        if not project.members.filter(id=request.user.id).exists():
            return Response({"error": "You cannot create tasks for this project"}, status=403)

        serializer = TaskSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(project=project)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=404)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_task(request, task_id):
    try:
        task = Task.objects.get(id=task_id)
        project_admin = task.project.created_by

        # Security: Admin ya Assigned User hi delete kar sake
        if project_admin != request.user:
            return Response({
                "error": "Access Denied: Only the Project Admin can delete tasks."
            }, status=403)
        task.delete()
        return Response({"msg": "Task deleted successfully"})

    except Task.DoesNotExist:
        return Response({"error": "Task not found"}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_project_tasks(request, pk):
    try:
        # check project exit or not
        project = Project.objects.get(pk=pk)

        # security: sirf project member hi dekh sakte hai task
        if not project.members.filter(id=request.user.id).exists():
            return Response({"error": "Access Denied"}, status=403)

        # Is project se jude saare tasks nikaalein
        # Yaad rakhein: Model mein 'related_name="tasks"' hona chahiye
        tasks = project.tasks.all()

        serializer = TaskSerializer(tasks, many=True, context={'request': request})
        return Response(serializer.data)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=404)


@api_view(['PATCH'])  # PATCH use hota hai partial update ke liye
@permission_classes([IsAuthenticated])
def update_task_status(request, pk):
    try:
        task = Task.objects.get(id=pk)
        project = task.project  # Task se project nikalien

        # Logic: Status sirf Assigned Member ya Project Admin hi badal sakta hai
        is_admin = (project.created_by == request.user)
        is_assignee = (task.assigned_to == request.user)

        if not (is_admin or is_assignee):
            return Response({"error": "You don't have permission to change this status"}, status=403)

        new_status = request.data.get('status')
        if new_status in ['To Do', 'In Progress', 'Done']:
            task.status = new_status
            task.save()
            return Response({"msg": "Status updated successfully", "new_status": task.status})

        return Response({"error": "Invalid status"}, status=400)

    except Task.DoesNotExist:
        return Response({"error": "Task not found"}, status=404)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_task(request, task_id):
    try:
        task = Task.objects.get(id=task_id)
        # Sirf Admin update kar sake
        if task.project.created_by != request.user:
            return Response({"error": "Unauthorized"}, status=403)

        serializer = TaskSerializer(task, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
    except Task.DoesNotExist:
        return Response({"error": "Task not found"}, status=404)