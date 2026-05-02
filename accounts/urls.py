from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('api/register/', views.RegisterView.as_view(), name='register'),
    path('api/login/', views.Login.as_view(), name='login'),
    path('api/check-username/', views.check_username, name='check_username'),
    path('api/check-auth/', views.check_auth_status, name='check_auth'),
    path('api/logout/', views.Logout.as_view(), name='check_auth'),
    path('api/profile_view/', views.profile_view, name='profile'),
    path('api/projects/create/', views.create_project, name='create_project'),
    path('api/projects/<int:pk>/delete/', views.delete_project),
    path('api/projects/', views.show_project, name='create_project'),
    path('api/dashboard-stats/', views.get_dashboard_stats, name='dashboard-stats'),
    path('api/projects/<int:pk>/', views.get_project_detail, name='project-detail'),
    path('api/projects/<int:pk>/add-member/', views.add_members, name='add-members'),
    path('api/tasks/create/', views.create_task, name='create-task'),
    path('api/tasks/<int:task_id>/delete/', views.delete_task),
    path('api/projects/<int:pk>/tasks/', views.get_project_tasks, name='project-tasks'),
    path('api/tasks/<int:pk>/update-status/', views.update_task_status, name='update-status'),
]
