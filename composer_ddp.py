import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
import torch.nn.functional as F
from composer import Trainer
from composer.models import ComposerModel
from composer.util import dist
from torch.utils.data.distributed import DistributedSampler

# Define the CNN model
class CIFAR10CNN(nn.Module):
    def __init__(self):
        super(CIFAR10CNN, self).__init__()
        self.conv1 = nn.Conv2d(3, 32, 3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
        self.conv3 = nn.Conv2d(64, 64, 3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.fc1 = nn.Linear(64 * 4 * 4, 512)
        self.fc2 = nn.Linear(512, 10)
        self.dropout = nn.Dropout(0.2)

    def forward(self, x):
        x = self.pool(torch.relu(self.conv1(x)))
        x = self.pool(torch.relu(self.conv2(x)))
        x = self.pool(torch.relu(self.conv3(x)))
        x = x.view(-1, 64 * 4 * 4)
        x = self.dropout(torch.relu(self.fc1(x)))
        x = self.fc2(x)
        return x

class ComposerCNN(ComposerModel):
    def __init__(self):
        super().__init__()
        self.model = CIFAR10CNN()

    def forward(self, batch):
        inputs, _ = batch
        return self.model(inputs)

    def loss(self, outputs, batch):
        _, targets = batch
        return F.cross_entropy(outputs, targets)

# Set random seed for reproducibility
torch.manual_seed(42)

# Initialize the distributed backend
dist.initialize_dist('gpu')

# Define transforms
transform = transforms.Compose([
    transforms.RandomHorizontalFlip(),
    transforms.RandomCrop(32, padding=4),
    transforms.ToTensor(),
    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
])

# Load CIFAR-10 dataset
trainset = torchvision.datasets.CIFAR10(root='./data', train=True, download=True, transform=transform)
testset = torchvision.datasets.CIFAR10(root='./data', train=False, download=True, transform=transform)

# Create distributed samplers
train_sampler = DistributedSampler(trainset, shuffle=True)
test_sampler = DistributedSampler(testset, shuffle=False)

# Create data loaders
trainloader = torch.utils.data.DataLoader(trainset, batch_size=32, sampler=train_sampler)
testloader = torch.utils.data.DataLoader(testset, batch_size=32, sampler=test_sampler)

# Define the model, loss function, and optimizer
model = ComposerCNN()
optimizer = optim.Adam(model.parameters(), lr=0.001)
num_epochs = 10

# Create the trainer
trainer = Trainer(
    model=model,
    train_dataloader=trainloader,
    optimizers=optimizer,
    max_duration=num_epochs,  # epochs
    device='gpu'
)

trainer.fit()
