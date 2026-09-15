#Ciao, questo è solo un test by MiLLA!
#Non c'è nulla di interessante qui.

'''

#° Passaggio che si fa una volta: digiti il tuo nome
$ git config --global username "MiLLA05355"  


#° Passaggio che si fa una volta: digiti la tua mail
$ git config --global user.email millazak@gmail.com   

#° Cloni il progetto prendendo il link da GitHub online
$ git clone https://github.com/80dan112libero/Suite-multimedia-Pro.git

#° Cambio directory sulla cartella del progetto
$ cd Suite-multimedia-Pro

#° Aggiungi file o file già esistente aggiornato
$ git add test_milla.py

#° Serve per creare un ramo, come se lavorassi in parallelo. Poi è il tutor che accetta o no
   l'aggiornamento fatto
git checkout -b MiLLA/test

#° Confermi il lavoro fatto fino a quel momento. Freeze le cose fatte
$ git commit -m "Ho testato il test"

#° Invii il file autenticandolo su GitHub online
$ git push origin MiLLA/test
'''

####°°°°°°°°°° ESEMPIO °°°°°°°°°°####


'''
utente@AULA2-2 MINGW64 ~
$ git config --global username "MiLLA05355"
error: key does not contain a section: username

utente@AULA2-2 MINGW64 ~
$ git config --global user.name MiLLA05355

utente@AULA2-2 MINGW64 ~
$ git config --global user.email millazak@gmail.com

utente@AULA2-2 MINGW64 ~
$ cd Desktop

utente@AULA2-2 MINGW64 ~/Desktop
$ git clone lone https://github.com/80dan112libero/Suite-multimedia-Pro.g
fatal: repository 'lone' does not exist

utente@AULA2-2 MINGW64 ~/Desktop
$ git clone lone https://github.com/80dan112libero/Suite-multimedia-Pro.git
fatal: repository 'lone' does not exist

utente@AULA2-2 MINGW64 ~/Desktop
$ git clone https://github.com/80dan112libero/Suite-multimedia-Pro.git
Cloning into 'Suite-multimedia-Pro'...
remote: Enumerating objects: 140, done.
remote: Counting objects: 100% (140/140), done.
remote: Compressing objects: 100% (131/131), done.
remote: Total 140 (delta 6), reused 134 (delta 3), pack-reused 0 (from 0)
Receiving objects: 100% (140/140), 20.22 MiB | 1.52 MiB/s, done.
Resolving deltas: 100% (6/6), done.

utente@AULA2-2 MINGW64 ~/Desktop
$ git add .
fatal: not a git repository (or any of the parent directories): .git

utente@AULA2-2 MINGW64 ~/Desktop
$ git checkout -b MiLLA/test
fatal: not a git repository (or any of the parent directories): .git

utente@AULA2-2 MINGW64 ~/Desktop
$ cd Suite-multimedia-Pro

utente@AULA2-2 MINGW64 ~/Desktop/Suite-multimedia-Pro (main)
$ git checkout -b MiLLA/test
Switched to a new branch 'MiLLA/test'

utente@AULA2-2 MINGW64 ~/Desktop/Suite-multimedia-Pro (MiLLA/test)
$ git commit -m "Ho testato il test"
On branch MiLLA/test
Untracked files:
  (use "git add <file>..." to include in what will be committed)
        test_milla.py

nothing added to commit but untracked files present (use "git add" to track)

utente@AULA2-2 MINGW64 ~/Desktop/Suite-multimedia-Pro (MiLLA/test)
$ git add test_milla.py

utente@AULA2-2 MINGW64 ~/Desktop/Suite-multimedia-Pro (MiLLA/test)
$ git commit -m "Ho testato il test."
[MiLLA/test ea74b40] Ho testato il test.
 1 file changed, 2 insertions(+)
 create mode 100644 test_milla.py

utente@AULA2-2 MINGW64 ~/Desktop/Suite-multimedia-Pro (MiLLA/test)
$ git push origin MiLLA/test
info: please complete authentication in your browser...
Enumerating objects: 4, done.
Counting objects: 100% (4/4), done.
Delta compression using up to 4 threads
Compressing objects: 100% (3/3), done.
Writing objects: 100% (3/3), 358 bytes | 358.00 KiB/s, done.
Total 3 (delta 1), reused 0 (delta 0), pack-reused 0 (from 0)
remote: Resolving deltas: 100% (1/1), completed with 1 local object.
remote:
remote: Create a pull request for 'MiLLA/test' on GitHub by visiting:
remote:      https://github.com/80dan112libero/Suite-multimedia-Pro/pull/new/MiLLA/test
remote:
To https://github.com/80dan112libero/Suite-multimedia-Pro.git
 * [new branch]      MiLLA/test -> MiLLA/test

utente@AULA2-2 MINGW64 ~/Desktop/Suite-multimedia-Pro (MiLLA/test)
$ git push origin MiLLA/test
Everything up-to-date
'''


