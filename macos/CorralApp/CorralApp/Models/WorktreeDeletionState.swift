import Foundation

@Observable
final class WorktreeDeletionState: Identifiable {
    let id: String
    let folderPath: String
    let folderLabel: String
    let sessionCount: Int

    enum Step: String, CaseIterable {
        case killingSessions = "Killing sessions"
        case runningPreDeleteScript = "Running pre-delete script"
        case removingWorktree = "Removing worktree"
        case deletingBranch = "Deleting branch"
    }

    enum StepStatus: Equatable {
        case pending, inProgress, completed, skipped, failed(String)
    }

    var stepStatuses: [Step: StepStatus]
    var currentStep: Step?
    var error: String?
    var isFinished = false

    init(folderPath: String, sessionCount: Int) {
        self.id = folderPath
        self.folderPath = folderPath
        self.folderLabel = URL(fileURLWithPath: folderPath).lastPathComponent
        self.sessionCount = sessionCount
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
