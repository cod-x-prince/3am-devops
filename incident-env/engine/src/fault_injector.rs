// Fault types for incident simulation

#[derive(Clone, Copy, Debug)]
pub enum FaultType {
    BadDeploy,
    MemoryLeak,
    CascadeTimeout,
    ThunderingHerd,
    SplitBrain,
    MultiFault,
    NetworkPartition,
    DiskFull,
}

impl FaultType {
    pub fn from_scenario(scenario: &str) -> Option<Self> {
        match scenario {
            "bad_deploy" => Some(FaultType::BadDeploy),
            "memory_leak" => Some(FaultType::MemoryLeak),
            "cascade_timeout" => Some(FaultType::CascadeTimeout),
            "thundering_herd" => Some(FaultType::ThunderingHerd),
            "split_brain" => Some(FaultType::SplitBrain),
            "multi_fault" => Some(FaultType::MultiFault),
            "network_partition" => Some(FaultType::NetworkPartition),
            "disk_full" => Some(FaultType::DiskFull),
            _ => None,
        }
    }
}
