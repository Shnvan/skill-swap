import React, { useState, useEffect } from 'react';
import { User, Plus, Star, Flag, CheckCircle, Clock, Search, Filter, AlertCircle, MessageSquare } from 'lucide-react';

// Mock data for wireframe
const mockUser = {
  id: "test-user-123",
  full_name: "John Doe",
  email: "john@example.com",
  skill: "Web Development",
  bio: "Experienced full-stack developer",
  is_active: true
};

const mockTasks = [
  {
    task_id: "1",
    title: "Build a landing page",
    description: "Need help creating a modern landing page for my startup",
    tags: ["web", "design", "react"],
    location: "Remote",
    time: "2024-01-15T14:00:00",
    status: "open",
    posted_by: "user-456",
    timestamp: "2024-01-10T10:00:00"
  },
  {
    task_id: "2", 
    title: "Photography for event",
    description: "Looking for photographer for wedding event",
    tags: ["photography", "wedding", "event"],
    location: "Manila",
    time: "2024-01-20T09:00:00",
    status: "open",
    posted_by: "user-789",
    timestamp: "2024-01-11T15:30:00"
  }
];

const mockRatings = [
  {
    rating_id: "1",
    from_user_id: "user-456",
    to_user_id: "test-user-123",
    task_id: "completed-1",
    rating: 5,
    comment: "Excellent work! Very professional and delivered on time.",
    timestamp: "2024-01-05T16:00:00"
  },
  {
    rating_id: "2",
    from_user_id: "user-789", 
    to_user_id: "test-user-123",
    task_id: "completed-2",
    rating: 4,
    comment: "Good communication and quality work.",
    timestamp: "2024-01-03T12:00:00"
  }
];

// API Service Layer (Mock Implementation)
const apiService = {
  // Users
  getProfile: async () => mockUser,
  updateProfile: async (data) => ({ ...mockUser, ...data }),
  
  // Tasks
  getOpenTasks: async () => ({ tasks: mockTasks, count: mockTasks.length }),
  getMyPostedTasks: async () => ({ tasks: [], count: 0 }),
  getMyAcceptedTasks: async () => ({ tasks: [], count: 0 }),
  createTask: async (task) => ({ ...task, task_id: Date.now().toString(), status: "open" }),
  acceptTask: async (taskId) => ({ message: "Task accepted successfully" }),
  completeTask: async (taskId) => ({ message: "Task completed successfully" }),
  
  // Ratings
  getMyRatings: async () => ({ 
    ratings: mockRatings, 
    statistics: { average_rating: 4.5, total_ratings: 2 }
  }),
  createRating: async (rating) => ({ ...rating, rating_id: Date.now().toString() }),
  
  // Reports
  createReport: async (report) => ({ ...report, report_id: Date.now().toString() })
};

// Header Component
const Header = ({ activeTab, setActiveTab, user }) => (
  <header className="bg-blue-600 text-white shadow-lg">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="flex justify-between items-center py-4">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center">
            <span className="text-blue-600 font-bold">SS</span>
          </div>
          <h1 className="text-2xl font-bold">SkillSwap</h1>
        </div>
        
        <nav className="hidden md:flex space-x-8">
          {['dashboard', 'my-tasks', 'profile', 'ratings'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab 
                  ? 'bg-blue-700 text-white' 
                  : 'text-blue-100 hover:bg-blue-500'
              }`}
            >
              {tab.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </button>
          ))}
        </nav>
        
        <div className="flex items-center space-x-3">
          <User className="w-6 h-6" />
          <span className="font-medium">{user?.full_name || 'Loading...'}</span>
        </div>
      </div>
    </div>
  </header>
);

// Dashboard Component
const Dashboard = () => {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTask, setSelectedTask] = useState(null);

  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const response = await apiService.getOpenTasks();
        setTasks(response.tasks);
      } catch (error) {
        console.error('Error fetching tasks:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchTasks();
  }, []);

  const filteredTasks = tasks.filter(task => 
    task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    task.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const handleAcceptTask = async (taskId) => {
    try {
      await apiService.acceptTask(taskId);
      alert('Task accepted successfully!');
      // Refresh tasks
      const response = await apiService.getOpenTasks();
      setTasks(response.tasks);
    } catch (error) {
      alert('Error accepting task');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Available Tasks</h2>
        <button className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2">
          <Plus className="w-4 h-4" />
          <span>Post Task</span>
        </button>
      </div>

      {/* Search and Filter */}
      <div className="flex space-x-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Search tasks by title or tags..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center space-x-2">
          <Filter className="w-4 h-4" />
          <span>Filters</span>
        </button>
      </div>

      {/* Tasks Grid */}
      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading available tasks...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTasks.map((task) => (
            <div key={task.task_id} className="bg-white rounded-lg shadow-md border border-gray-200 p-6 hover:shadow-lg transition-shadow">
              <div className="flex justify-between items-start mb-3">
                <h3 className="text-lg font-semibold text-gray-900 line-clamp-2">{task.title}</h3>
                <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">
                  {task.status}
                </span>
              </div>
              
              <p className="text-gray-600 mb-4 line-clamp-3">{task.description}</p>
              
              <div className="flex flex-wrap gap-2 mb-4">
                {task.tags.map((tag, index) => (
                  <span key={index} className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full">
                    {tag}
                  </span>
                ))}
              </div>
              
              <div className="flex justify-between items-center text-sm text-gray-500 mb-4">
                <span>📍 {task.location || 'Remote'}</span>
                <span>⏰ {new Date(task.timestamp).toLocaleDateString()}</span>
              </div>
              
              <div className="flex space-x-3">
                <button 
                  onClick={() => handleAcceptTask(task.task_id)}
                  className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors text-sm font-medium"
                >
                  Accept Task
                </button>
                <button 
                  onClick={() => setSelectedTask(task)}
                  className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 text-sm"
                >
                  Details
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {filteredTasks.length === 0 && !loading && (
        <div className="text-center py-12">
          <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No tasks found</h3>
          <p className="text-gray-600">Try adjusting your search or check back later for new tasks.</p>
        </div>
      )}

      {/* Task Detail Modal */}
      {selectedTask && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-90vh overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-start mb-4">
                <h3 className="text-xl font-bold text-gray-900">{selectedTask.title}</h3>
                <button 
                  onClick={() => setSelectedTask(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <h4 className="font-semibold text-gray-900 mb-2">Description</h4>
                  <p className="text-gray-600">{selectedTask.description}</p>
                </div>
                
                <div>
                  <h4 className="font-semibold text-gray-900 mb-2">Tags</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedTask.tags.map((tag, index) => (
                      <span key={index} className="bg-blue-100 text-blue-800 text-sm px-3 py-1 rounded-full">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h4 className="font-semibold text-gray-900 mb-1">Location</h4>
                    <p className="text-gray-600">{selectedTask.location || 'Remote'}</p>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-900 mb-1">Posted</h4>
                    <p className="text-gray-600">{new Date(selectedTask.timestamp).toLocaleDateString()}</p>
                  </div>
                </div>
                
                <div className="flex space-x-3 pt-4">
                  <button 
                    onClick={() => {
                      handleAcceptTask(selectedTask.task_id);
                      setSelectedTask(null);
                    }}
                    className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors"
                  >
                    Accept This Task
                  </button>
                  <button 
                    onClick={() => setSelectedTask(null)}
                    className="px-6 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// My Tasks Component
const MyTasks = () => {
  const [activeTaskTab, setActiveTaskTab] = useState('posted');
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTask, setNewTask] = useState({
    title: '',
    description: '',
    tags: '',
    location: '',
    time: ''
  });

  useEffect(() => {
    const fetchTasks = async () => {
      setLoading(true);
      try {
        let response;
        if (activeTaskTab === 'posted') {
          response = await apiService.getMyPostedTasks();
        } else {
          response = await apiService.getMyAcceptedTasks();
        }
        setTasks(response.tasks);
      } catch (error) {
        console.error('Error fetching tasks:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchTasks();
  }, [activeTaskTab]);

  const handleCreateTask = async (e) => {
    e.preventDefault();
    try {
      const taskData = {
        ...newTask,
        tags: newTask.tags.split(',').map(tag => tag.trim()).filter(tag => tag)
      };
      await apiService.createTask(taskData);
      alert('Task created successfully!');
      setShowCreateForm(false);
      setNewTask({ title: '', description: '', tags: '', location: '', time: '' });
      // Refresh tasks
      const response = await apiService.getMyPostedTasks();
      setTasks(response.tasks);
    } catch (error) {
      alert('Error creating task');
    }
  };

  const handleCompleteTask = async (taskId) => {
    try {
      await apiService.completeTask(taskId);
      alert('Task marked as completed!');
      // Refresh tasks
      const response = await apiService.getMyAcceptedTasks();
      setTasks(response.tasks);
    } catch (error) {
      alert('Error completing task');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">My Tasks</h2>
        <button 
          onClick={() => setShowCreateForm(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
        >
          <Plus className="w-4 h-4" />
          <span>Create Task</span>
        </button>
      </div>

      {/* Task Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {[
            { key: 'posted', label: 'Posted by Me', icon: Plus },
            { key: 'accepted', label: 'Accepted by Me', icon: CheckCircle }
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTaskTab(key)}
              className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                activeTaskTab === key
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tasks List */}
      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading your tasks...</p>
        </div>
      ) : (
        <div className="space-y-4">
          {tasks.length === 0 ? (
            <div className="text-center py-12">
              <Clock className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No tasks found</h3>
              <p className="text-gray-600">
                {activeTaskTab === 'posted' 
                  ? 'You haven\'t posted any tasks yet. Create one to get started!' 
                  : 'You haven\'t accepted any tasks yet. Browse available tasks to help others!'}
              </p>
            </div>
          ) : (
            tasks.map((task) => (
              <div key={task.task_id} className="bg-white rounded-lg shadow-md border border-gray-200 p-6">
                <div className="flex justify-between items-start mb-3">
                  <h3 className="text-lg font-semibold text-gray-900">{task.title}</h3>
                  <div className="flex items-center space-x-2">
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      task.status === 'open' ? 'bg-green-100 text-green-800' :
                      task.status === 'accepted' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-blue-100 text-blue-800'
                    }`}>
                      {task.status}
                    </span>
                  </div>
                </div>
                
                <p className="text-gray-600 mb-4">{task.description}</p>
                
                <div className="flex flex-wrap gap-2 mb-4">
                  {task.tags.map((tag, index) => (
                    <span key={index} className="bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded-full">
                      {tag}
                    </span>
                  ))}
                </div>
                
                <div className="flex justify-between items-center">
                  <div className="text-sm text-gray-500">
                    <span>📍 {task.location || 'Remote'}</span>
                    <span className="ml-4">⏰ {new Date(task.timestamp).toLocaleDateString()}</span>
                  </div>
                  
                  {activeTaskTab === 'accepted' && task.status === 'accepted' && (
                    <button 
                      onClick={() => handleCompleteTask(task.task_id)}
                      className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 transition-colors text-sm"
                    >
                      Mark Complete
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Create Task Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-90vh overflow-y-auto">
            <form onSubmit={handleCreateTask} className="p-6">
              <h3 className="text-xl font-bold text-gray-900 mb-6">Create New Task</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Title *</label>
                  <input
                    type="text"
                    required
                    value={newTask.title}
                    onChange={(e) => setNewTask({...newTask, title: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Brief but descriptive title"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
                  <textarea
                    required
                    rows={4}
                    value={newTask.description}
                    onChange={(e) => setNewTask({...newTask, description: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Explain what needs to be done..."
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Tags * (comma-separated)</label>
                  <input
                    type="text"
                    required
                    value={newTask.tags}
                    onChange={(e) => setNewTask({...newTask, tags: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="web, design, programming"
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
                    <input
                      type="text"
                      value={newTask.location}
                      onChange={(e) => setNewTask({...newTask, location: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="Remote or specific location"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Preferred Time</label>
                    <input
                      type="datetime-local"
                      value={newTask.time}
                      onChange={(e) => setNewTask({...newTask, time: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>
              </div>
              
              <div className="flex space-x-3 pt-6">
                <button 
                  type="submit"
                  className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors"
                >
                  Create Task
                </button>
                <button 
                  type="button"
                  onClick={() => setShowCreateForm(false)}
                  className="px-6 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

// Profile Component
const Profile = () => {
  const [user, setUser] = useState(mockUser);
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    full_name: user.full_name,
    skill: user.skill,
    bio: user.bio || ''
  });

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    try {
      const updatedUser = await apiService.updateProfile(editForm);
      setUser(updatedUser);
      setIsEditing(false);
      alert('Profile updated successfully!');
    } catch (error) {
      alert('Error updating profile');
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h2 className="text-3xl font-bold text-gray-900">My Profile</h2>
      
      <div className="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden">
        <div className="bg-gradient-to-r from-blue-500 to-purple-600 h-32"></div>
        
        <div className="relative px-6 pb-6">
          <div className="absolute -top-16 left-6">
            <div className="w-32 h-32 bg-white rounded-full border-4 border-white shadow-lg flex items-center justify-center">
              <User className="w-16 h-16 text-gray-400" />
            </div>
          </div>
          
          <div className="pt-20">
            {isEditing ? (
              <form onSubmit={handleSaveProfile} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                  <input
                    type="text"
                    value={editForm.full_name}
                    onChange={(e) => setEditForm({...editForm, full_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Skill</label>
                  <input
                    type="text"
                    value={editForm.skill}
                    onChange={(e) => setEditForm({...editForm, skill: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Bio</label>
                  <textarea
                    rows={3}
                    value={editForm.bio}
                    onChange={(e) => setEditForm({...editForm, bio: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                    placeholder="Tell others about yourself..."
                  />
                </div>
                
                <div className="flex space-x-3">
                  <button 
                    type="submit"
                    className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
                  >
                    Save Changes
                  </button>
                  <button 
                    type="button"
                    onClick={() => setIsEditing(false)}
                    className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            ) : (
              <div>
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-2xl font-bold text-gray-900">{user.full_name}</h3>
                    <p className="text-lg text-blue-600 font-medium">{user.skill}</p>
                    <p className="text-gray-600 mt-2">{user.bio || 'No bio provided yet.'}</p>
                  </div>
                  <button 
                    onClick={() => setIsEditing(true)}
                    className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
                  >
                    Edit Profile
                  </button>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6 pt-6 border-t border-gray-200">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">0</div>
                    <div className="text-sm text-gray-500">Tasks Posted</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">0</div>
                    <div className="text-sm text-gray-500">Tasks Completed</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-yellow-600">4.5</div>
                    <div className="text-sm text-gray-500">Average Rating</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Ratings Component
const Ratings = () => {
  const [ratings, setRatings] = useState([]);
  const [statistics, setStatistics] = useState({ average_rating: 0, total_ratings: 0 });
  const [loading, setLoading] = useState(true);
  const [showRatingForm, setShowRatingForm] = useState(false);
  const [newRating, setNewRating] = useState({
    to_user_id: '',
    task_id: '',
    rating: 5,
    comment: ''
  });

  useEffect(() => {
    const fetchRatings = async () => {
      try {
        const response = await apiService.getMyRatings();
        setRatings(response.ratings);
        setStatistics(response.statistics);
      } catch (error) {
        console.error('Error fetching ratings:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchRatings();
  }, []);

  const handleCreateRating = async (e) => {
    e.preventDefault();
    try {
      await apiService.createRating(newRating);
      alert('Rating submitted successfully!');
      setShowRatingForm(false);
      setNewRating({ to_user_id: '', task_id: '', rating: 5, comment: '' });
      // Refresh ratings
      const response = await apiService.getMyRatings();
      setRatings(response.ratings);
      setStatistics(response.statistics);
    } catch (error) {
      alert('Error submitting rating');
    }
  };

  const renderStars = (rating) => {
    return [...Array(5)].map((_, i) => (
      <Star
        key={i}
        className={`w-4 h-4 ${i < rating ? 'text-yellow-400 fill-current' : 'text-gray-300'}`}
      />
    ));
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Ratings & Reviews</h2>
        <button 
          onClick={() => setShowRatingForm(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
        >
          <Star className="w-4 h-4" />
          <span>Rate Someone</span>
        </button>
      </div>

      {/* Rating Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg shadow-md border border-gray-200 p-6 text-center">
          <div className="text-3xl font-bold text-blue-600 mb-2">{statistics.average_rating}</div>
          <div className="flex justify-center mb-2">
            {renderStars(Math.round(statistics.average_rating))}
          </div>
          <div className="text-sm text-gray-500">Average Rating</div>
        </div>
        
        <div className="bg-white rounded-lg shadow-md border border-gray-200 p-6 text-center">
          <div className="text-3xl font-bold text-green-600 mb-2">{statistics.total_ratings}</div>
          <div className="text-sm text-gray-500">Total Reviews</div>
        </div>
        
        <div className="bg-white rounded-lg shadow-md border border-gray-200 p-6 text-center">
          <div className="text-3xl font-bold text-purple-600 mb-2">98%</div>
          <div className="text-sm text-gray-500">Positive Feedback</div>
        </div>
      </div>

      {/* Ratings List */}
      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading your ratings...</p>
        </div>
      ) : (
        <div className="space-y-4">
          <h3 className="text-xl font-semibold text-gray-900">Recent Reviews</h3>
          
          {ratings.length === 0 ? (
            <div className="text-center py-12">
              <Star className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No ratings yet</h3>
              <p className="text-gray-600">Complete some tasks to start receiving ratings!</p>
            </div>
          ) : (
            ratings.map((rating) => (
              <div key={rating.rating_id} className="bg-white rounded-lg shadow-md border border-gray-200 p-6">
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center">
                      <User className="w-6 h-6 text-gray-500" />
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">User {rating.from_user_id.slice(-3)}</div>
                      <div className="text-sm text-gray-500">{new Date(rating.timestamp).toLocaleDateString()}</div>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <div className="flex">
                      {renderStars(rating.rating)}
                    </div>
                    <button className="text-gray-400 hover:text-red-500">
                      <Flag className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                
                {rating.comment && (
                  <p className="text-gray-600 mb-3">{rating.comment}</p>
                )}
                
                <div className="text-sm text-gray-500">
                  Task ID: {rating.task_id}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Create Rating Modal */}
      {showRatingForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-md w-full">
            <form onSubmit={handleCreateRating} className="p-6">
              <h3 className="text-xl font-bold text-gray-900 mb-6">Rate a User</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">User ID *</label>
                  <input
                    type="text"
                    required
                    value={newRating.to_user_id}
                    onChange={(e) => setNewRating({...newRating, to_user_id: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter user ID to rate"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Task ID *</label>
                  <input
                    type="text"
                    required
                    value={newRating.task_id}
                    onChange={(e) => setNewRating({...newRating, task_id: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter task ID"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Rating *</label>
                  <div className="flex space-x-2">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button
                        key={star}
                        type="button"
                        onClick={() => setNewRating({...newRating, rating: star})}
                        className="focus:outline-none"
                      >
                        <Star
                          className={`w-8 h-8 ${star <= newRating.rating ? 'text-yellow-400 fill-current' : 'text-gray-300'}`}
                        />
                      </button>
                    ))}
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Comment</label>
                  <textarea
                    rows={3}
                    value={newRating.comment}
                    onChange={(e) => setNewRating({...newRating, comment: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                    placeholder="Share your experience (optional)"
                  />
                </div>
              </div>
              
              <div className="flex space-x-3 pt-6">
                <button 
                  type="submit"
                  className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700"
                >
                  Submit Rating
                </button>
                <button 
                  type="button"
                  onClick={() => setShowRatingForm(false)}
                  className="px-6 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

// Reports Component (Simplified for wireframe)
const Reports = () => {
  const [showReportForm, setShowReportForm] = useState(false);
  const [newReport, setNewReport] = useState({
    to_user_id: '',
    task_id: '',
    reason: ''
  });

  const handleCreateReport = async (e) => {
    e.preventDefault();
    try {
      await apiService.createReport(newReport);
      alert('Report submitted successfully!');
      setShowReportForm(false);
      setNewReport({ to_user_id: '', task_id: '', reason: '' });
    } catch (error) {
      alert('Error submitting report');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Reports</h2>
        <button 
          onClick={() => setShowReportForm(true)}
          className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors flex items-center space-x-2"
        >
          <Flag className="w-4 h-4" />
          <span>Report Issue</span>
        </button>
      </div>

      <div className="bg-white rounded-lg shadow-md border border-gray-200 p-6">
        <div className="text-center py-12">
          <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No reports found</h3>
          <p className="text-gray-600">You haven't submitted any reports yet.</p>
        </div>
      </div>

      {/* Create Report Modal */}
      {showReportForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-md w-full">
            <form onSubmit={handleCreateReport} className="p-6">
              <h3 className="text-xl font-bold text-gray-900 mb-6">Report an Issue</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">User ID *</label>
                  <input
                    type="text"
                    required
                    value={newReport.to_user_id}
                    onChange={(e) => setNewReport({...newReport, to_user_id: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter user ID to report"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Task ID *</label>
                  <input
                    type="text"
                    required
                    value={newReport.task_id}
                    onChange={(e) => setNewReport({...newReport, task_id: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter related task ID"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Reason *</label>
                  <textarea
                    required
                    rows={4}
                    value={newReport.reason}
                    onChange={(e) => setNewReport({...newReport, reason: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
                    placeholder="Please provide detailed information about the issue..."
                  />
                </div>
              </div>
              
              <div className="flex space-x-3 pt-6">
                <button 
                  type="submit"
                  className="flex-1 bg-red-600 text-white py-2 px-4 rounded-md hover:bg-red-700"
                >
                  Submit Report
                </button>
                <button 
                  type="button"
                  onClick={() => setShowReportForm(false)}
                  className="px-6 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

// Main App Component
const SkillSwapApp = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUserProfile = async () => {
      try {
        const profile = await apiService.getProfile();
        setUser(profile);
      } catch (error) {
        console.error('Error fetching profile:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchUserProfile();
  }, []);

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard />;
      case 'my-tasks':
        return <MyTasks />;
      case 'profile':
        return <Profile />;
      case 'ratings':
        return <Ratings />;
      case 'reports':
        return <Reports />;
      default:
        return <Dashboard />;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading SkillSwap...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header activeTab={activeTab} setActiveTab={setActiveTab} user={user} />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {renderContent()}
      </main>
      
      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="text-center text-gray-500 text-sm">
            <p>&copy; 2024 SkillSwap. Connecting people through skills and collaboration.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default SkillSwapApp;