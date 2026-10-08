import { useCallback, useEffect, useMemo, useState } from 'react';
import type { QualityTask, TaskDraft } from '../types';
import { taskStorage } from '../services/storage';
import { createTask, refreshTask } from '../features/taskFactory';

export function useTasks() {
  const [tasks, setTasks] = useState<QualityTask[]>([]);
  const [message, setMessage] = useState('已自动保存');

  useEffect(() => {
    setTasks(taskStorage.load());
  }, []);

  const persist = useCallback((next: QualityTask[]) => {
    taskStorage.save(next);
    setTasks(next);
    setMessage(`已自动保存 ${new Date().toLocaleTimeString()}`);
  }, []);

  const addTask = useCallback((draft: TaskDraft) => {
    const task = createTask(draft);
    persist([task, ...taskStorage.load().filter((item) => item.id !== task.id)]);
    return task;
  }, [persist]);

  const updateTask = useCallback((task: QualityTask) => {
    const refreshed = refreshTask(task);
    persist([refreshed, ...taskStorage.load().filter((item) => item.id !== task.id)]);
    return refreshed;
  }, [persist]);

  const deleteTask = useCallback((taskId: string) => {
    persist(taskStorage.load().filter((task) => task.id !== taskId));
  }, [persist]);

  const stats = useMemo(() => {
    const caseCount = tasks.reduce((sum, task) => sum + task.testCases.length, 0);
    const p0Count = tasks.reduce((sum, task) => sum + task.testCases.filter((item) => item.priority === 'P0').length, 0);
    const average = tasks.length === 0 ? 0 : Math.round(tasks.reduce((sum, task) => sum + task.coverage.overall, 0) / tasks.length);
    return { taskCount: tasks.length, caseCount, p0Count, average };
  }, [tasks]);

  return { tasks, stats, message, addTask, updateTask, deleteTask };
}
