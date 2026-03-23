import Foundation

@Observable
final class WorktreeCreationState: Identifiable {
    let id: String
    let branchName: String
    let repoDisplayName: String
    let worktreePath: String

    enum Step: String, CaseIterable {
        case creatingWorktree = "Creating worktree"
        case runningSetupScript = "Running setup script"
        case launchingAgent = "Launching agent"
    }

    enum StepStatus: Equatable {
        case pending, inProgress, completed, skipped, failed(String)
    }

    var stepStatuses: [Step: StepStatus]
    var currentStep: Step?
    var error: String?
    var isFinished = false

    init(branchName: String, repoDisplayName: String, worktreePath: String) {
        self.id = "placeholder-\(UUID().uuidString)"
        self.branchName = branchName
        self.repoDisplayName = repoDisplayName
        self.worktreePath = worktreePath
        self.stepStatuses = Dictionary(uniqueKeysWithValues: Step.allCases.map { ($0, StepStatus.pending) })
    }

    func advance(to step: Step) {
        if let current = currentStep {
            stepStatuses[current] = .completed
        }
        currentStep = step
        stepStatuses[step] = .inProgress
    }

    func skipStep(_ step: Step) {
        stepStatuses[step] = .skipped
    }

    func completeCurrentStep() {
        if let current = currentStep {
            stepStatuses[current] = .completed
        }
    }

    func fail(at step: Step, message: String) {
        stepStatuses[step] = .failed(message)
        currentStep = nil
        error = message
    }
}
