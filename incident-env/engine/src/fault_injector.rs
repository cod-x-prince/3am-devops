use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum FaultType {
    CpuSpike,
    MemoryLeak,
    NetworkPartition,
    DbDeadlock,
    BadDeploy,
    ThunderingHerd,
    CascadeTimeout,
    SplitBrain,
}

impl FaultType {
    pub fn from_name(name: &str) -> Option<Self> {
        match name {
            "CpuSpike" => Some(Self::CpuSpike),
            "MemoryLeak" => Some(Self::MemoryLeak),
            "NetworkPartition" => Some(Self::NetworkPartition),
            "DbDeadlock" => Some(Self::DbDeadlock),
            "BadDeploy" => Some(Self::BadDeploy),
            "ThunderingHerd" => Some(Self::ThunderingHerd),
            "CascadeTimeout" => Some(Self::CascadeTimeout),
            "SplitBrain" => Some(Self::SplitBrain),
            _ => None,
        }
    }
}
